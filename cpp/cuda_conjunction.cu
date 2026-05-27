/*
 * cpp/cuda_conjunction.cu — CUDA All-Pairs Conjunction Screening
 * ==============================================================
 */
#include "cuda_bridge.h"
#include "cuda_physics.cuh"
#include <cuda_runtime.h>
#include <cmath>
#include <vector>
#include <stdexcept>
#include <string>

#define CUDA_CHECK(call) \
    do { cudaError_t _e=(call); if(_e!=cudaSuccess) \
        throw std::runtime_error(std::string("CUDA: ")+cudaGetErrorString(_e) \
            +" at " __FILE__ ":"+std::to_string(__LINE__)); } while(0)

// Thresholds
__constant__ double C_CRIT = 0.1;   // km
__constant__ double C_WARN = 1.0;   // km
__constant__ double C_ADV  = 5.0;   // km

// ── Result struct for GPU output ──────────────────────────────────────────────
struct GpuWarning {
    int sat_id, deb_id;
    double min_dist, tca;
    double rel_vx, rel_vy, rel_vz;
    int severity; // 0=none, 1=advisory, 2=warning, 3=critical
};

// ── Pre-propagate all states for the full lookahead window ──
// Stores in SoA layout per timestep: step(comp(n)) = s*6*n + c*n + i
// This allows coalesced reads by the scan kernel and eliminates the
// O(ns*nd) redundant propagations from the per-pair approach.
__global__ void k_prepropagate(
    const double* __restrict__ states_in,
    double* __restrict__ states_out,
    int n, double dt, int steps, double mjd0) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;

    double x = states_in[i*6],   y = states_in[i*6+1], z = states_in[i*6+2];
    double vx = states_in[i*6+3],vy = states_in[i*6+4],vz = states_in[i*6+5];

    int cs = n;
    int ss = cs * 6;

    for (int s = 0; s <= steps; s++) {
        int base = s * ss;
        states_out[base + 0*cs + i] = x;
        states_out[base + 1*cs + i] = y;
        states_out[base + 2*cs + i] = z;
        states_out[base + 3*cs + i] = vx;
        states_out[base + 4*cs + i] = vy;
        states_out[base + 5*cs + i] = vz;

        if (s < steps)
            rk4_step_device(x, y, z, vx, vy, vz, dt, false, 0, 1, 0, 1.5, mjd0, s);
    }
}

// ── Scan pre-propagated trajectory for closest approach ─────
// Both arrays are in SoA layout: step0[X0..Xn-1,Y0..Yn-1,...], step1[...]
// All threads in a warp access consecutive addresses — fully coalesced.
__global__ void k_scan_pairs(
    const double* __restrict__ sats_full, int ns,
    const double* __restrict__ debs_full, int nd,
    int nsteps, double step_s,
    GpuWarning* __restrict__ out,
    int* __restrict__ out_count,
    int max_out) {
    int si = blockIdx.x * blockDim.x + threadIdx.x;
    int di = blockIdx.y * blockDim.y + threadIdx.y;
    if (si >= ns || di >= nd) return;

    double min_dist = 1e15, tca = 0.0;
    double rv_x = 0, rv_y = 0, rv_z = 0;
    int s_stride = ns * 6;
    int d_stride = nd * 6;

    for (int st = 0; st <= nsteps; st++) {
        int sb = st * s_stride;
        int db = st * d_stride;
        double rx = sats_full[sb + si] - debs_full[db + di];
        double ry = sats_full[sb + ns + si] - debs_full[db + nd + di];
        double rz = sats_full[sb + 2*ns + si] - debs_full[db + 2*nd + di];
        double d2 = rx*rx + ry*ry + rz*rz;
        if (d2 < min_dist) {
            min_dist = d2;
            tca = st * step_s;
            rv_x = sats_full[sb + 3*ns + si] - debs_full[db + 3*nd + di];
            rv_y = sats_full[sb + 4*ns + si] - debs_full[db + 4*nd + di];
            rv_z = sats_full[sb + 5*ns + si] - debs_full[db + 5*nd + di];
        }
    }

    double d = sqrt(min_dist);
    int sev = 0;
    if      (d < C_CRIT) sev = 3;
    else if (d < C_WARN) sev = 2;
    else if (d < C_ADV)  sev = 1;
    if (sev == 0) return;

    int idx = atomicAdd(out_count, 1);
    if (idx < max_out) {
        out[idx] = {si, di, d, tca, rv_x, rv_y, rv_z, sev};
    }
}

#ifdef USE_CUDA
// ── Host launcher ─────────────────────────────────────────────────────────────
std::vector<ConjunctionWarning> cuda_detect_conjunctions(
        const double* sat_states, int ns,
        const double* debris_states, int nd,
        double lookahead_s, double step_s, double mjd0) {

    if (ns == 0 || nd == 0) return {};

    int nsteps = (int)(lookahead_s / step_s);
    int max_out = std::max(ns * nd / 10, 1024);

    // Input buffers (AoS)
    DeviceMem ds(ns*6*sizeof(double));
    DeviceMem dd(nd*6*sizeof(double));
    CUDA_CHECK(cudaMemcpy(ds.ptr, sat_states, ns*6*sizeof(double), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(dd.ptr, debris_states, nd*6*sizeof(double), cudaMemcpyHostToDevice));

    // Phase 1: Pre-propagate all states for full lookahead window
    // Output buffers in SoA layout per timestep: (steps+1) × 6 × n × 8 bytes
    size_t sat_full_bytes = (size_t)(nsteps + 1) * ns * 6 * sizeof(double);
    size_t deb_full_bytes = (size_t)(nsteps + 1) * nd * 6 * sizeof(double);
    DeviceMem ds_full(sat_full_bytes);
    DeviceMem dd_full(deb_full_bytes);

    int blk = 256;
    k_prepropagate<<<(ns + blk - 1) / blk, blk>>>(
        (double*)ds.ptr, (double*)ds_full.ptr, ns, step_s, nsteps, mjd0);
    k_prepropagate<<<(nd + blk - 1) / blk, blk>>>(
        (double*)dd.ptr, (double*)dd_full.ptr, nd, step_s, nsteps, mjd0);
    CUDA_CHECK(cudaGetLastError());

    // Phase 2: Distance-only scan over all pairs
    DeviceMem cnt(sizeof(int));
    DeviceMem gout(max_out*sizeof(GpuWarning));
    CUDA_CHECK(cudaMemset(cnt.ptr, 0, sizeof(int)));

    dim3 blk2(16, 16), grd2((ns+15)/16, (nd+15)/16);
    k_scan_pairs<<<grd2, blk2>>>(
        (double*)ds_full.ptr, ns, (double*)dd_full.ptr, nd,
        nsteps, step_s,
        (GpuWarning*)gout.ptr, (int*)cnt.ptr, max_out);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());

    int h_cnt = 0;
    CUDA_CHECK(cudaMemcpy(&h_cnt, cnt.ptr, sizeof(int), cudaMemcpyDeviceToHost));
    h_cnt = std::min(h_cnt, max_out);

    std::vector<GpuWarning> hw(h_cnt);
    if (h_cnt > 0)
        CUDA_CHECK(cudaMemcpy(hw.data(), gout.ptr, h_cnt*sizeof(GpuWarning), cudaMemcpyDeviceToHost));

    static const Severity SEV[] = {Severity::NONE, Severity::ADVISORY, Severity::WARNING, Severity::CRITICAL};
    std::vector<ConjunctionWarning> result;
    result.reserve(h_cnt);
    for (auto& w : hw) {
        ConjunctionWarning cw;
        cw.sat_id = w.sat_id; cw.debris_id = w.deb_id;
        cw.current_distance = w.min_dist;
        cw.time_to_closest_approach = w.tca;
        cw.severity = (w.severity >= 0 && w.severity <= 3) ? SEV[w.severity] : Severity::NONE;
        cw.relative_velocity = {w.rel_vx, w.rel_vy, w.rel_vz};
        result.push_back(cw);
    }
    return result;
}
#endif
