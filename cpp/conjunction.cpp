/*
 * cpp/conjunction.cpp — C++ Conjunction Detector
 * ===============================================
 * All-pairs screening with:
 *   - Pre-propagation of all objects (batch, full history) — avoids per-pair
 *     re-propagation during the coarse sweep (was O(ns*nd*steps) RK4 calls,
 *     now O((ns+nd)*steps) + O(ns*nd*steps) distance-only checks).
 *   - Broad-phase spatial culling based on initial pair separation.
 *   - Brent's method for sub-step TCA refinement.
 *   - ADVISORY / WARNING / CRITICAL severity tiers.
 *   - Chan's method Probability of Collision (Pc).
 */
#include "conjunction.h"
#include "propagator.h"
#include <cmath>
#include <algorithm>
#include <cstring>


ConjunctionDetector::ConjunctionDetector() {}

// ── Brent's Method for 1D minimisation ───────────────────────────────────────
// Finds the x in [a,b] minimising f(x) to tolerance tol using Brent's method.
// See: Brent (1973) "Algorithms for Minimization without Derivatives"
template<typename F>
static double brent_minimise(F&& f, double a, double b, double tol = 0.01) {
    constexpr double GOLDEN = 0.3819660;
    double x = a + GOLDEN * (b - a);
    double w = x, v = x;
    double fx = f(x), fw = fx, fv = fx;
    double d = 0.0, e = 0.0;

    for (int iter = 0; iter < 50; ++iter) {
        double m = 0.5 * (a + b);
        double tol1 = tol * std::abs(x) + 1e-10;
        double tol2 = 2.0 * tol1;
        if (std::abs(x - m) <= tol2 - 0.5 * (b - a)) break;

        bool do_golden = true;
        if (std::abs(e) > tol1) {
            double r = (x - w) * (fx - fv);
            double q = (x - v) * (fx - fw);
            double p = (x - v) * q - (x - w) * r;
            q = 2.0 * (q - r);
            if (q > 0) p = -p; else q = -q;
            r = e; e = d;
            if (std::abs(p) < std::abs(0.5 * q * r) &&
                p > q * (a - x) && p < q * (b - x)) {
                d = p / q;
                double u = x + d;
                if ((u - a) < tol2 || (b - u) < tol2)
                    d = (x < m) ? tol1 : -tol1;
                do_golden = false;
            }
        }
        if (do_golden) {
            e = (x < m) ? b - x : a - x;
            d = GOLDEN * e;
        }
        double u = x + ((std::abs(d) >= tol1) ? d : (d > 0 ? tol1 : -tol1));
        double fu = f(u);
        if (fu <= fx) {
            if (u < x) b = x; else a = x;
            v = w; fv = fw; w = x; fw = fx; x = u; fx = fu;
        } else {
            if (u < x) a = u; else b = u;
            if (fu <= fw || w == x) { v = w; fv = fw; w = u; fw = fu; }
            else if (fu <= fv || v == x || v == w) { v = u; fv = fu; }
        }
    }
    return x;
}

// ── Chan's Pc: 2D Gaussian integral (Foster 1992 / Chan 1997 formulation) ────
// Uses the combined covariance at TCA modelled as a diagonal 2D ellipse in the
// miss-distance plane. sigma_r is the combined 1-sigma position uncertainty [km].
// Returns Pc using the series expansion for the circular encounter approximation.
static PcResult chan_pc(double miss_dist_km, double sigma_r_km,
                        double rel_speed_km_s, double hard_body_radius_km = 0.01) {
    PcResult r;
    r.sigma_pos_km = sigma_r_km;
    r.computed = false;
    if (sigma_r_km <= 0 || rel_speed_km_s <= 0) return r;

    double x = miss_dist_km / sigma_r_km;
    double sigma2 = sigma_r_km * sigma_r_km;
    double hbr2 = hard_body_radius_km * hard_body_radius_km;
    double pc = (hbr2 / (2.0 * sigma2)) * std::exp(-0.5 * x * x);
    r.pc = std::min(pc, 1.0);
    r.computed = true;
    return r;
}

std::vector<ConjunctionWarning> ConjunctionDetector::detect(
    const std::vector<StateVector>& sat_states,
    const std::vector<StateVector>& debris_states,
    double lookahead_s,
    double step_s,
    double tle_age_days) const {

    std::vector<ConjunctionWarning> warnings;
    Propagator prop;

    int ns = (int)sat_states.size();
    int nd = (int)debris_states.size();
    if (ns == 0 || nd == 0) return warnings;

    // ── 1. Pre-propagate all objects (batch full history) ──────────────────
    // Flat layout: (steps+1, n, 6) = n_frames × n_objects × 6 doubles.
    // Offset for step t, object i, component k: t * (n * 6) + i * 6 + k.
    int64_t steps = (int64_t)(lookahead_s / step_s);
    int64_t n_frames = steps + 1;

    std::vector<double> init_sats(ns * 6);
    std::vector<double> init_debs(nd * 6);
    for (int i = 0; i < ns; ++i)
        std::memcpy(&init_sats[(size_t)i * 6], sat_states[i].raw(), 6 * sizeof(double));
    for (int i = 0; i < nd; ++i)
        std::memcpy(&init_debs[(size_t)i * 6], debris_states[i].raw(), 6 * sizeof(double));

    std::vector<double> sat_history(n_frames * ns * 6);
    std::vector<double> deb_history(n_frames * nd * 6);

    prop.batch_propagate_full_history(init_sats.data(), ns, step_s, steps,
                                       0.0, 1.0, 2.2, 1.5, false, 0.0,
                                       sat_history.data());
    prop.batch_propagate_full_history(init_debs.data(), nd, step_s, steps,
                                       0.0, 1.0, 2.2, 1.5, false, 0.0,
                                       deb_history.data());

    // ── 2. Broad-phase filter ──────────────────────────────────────────────
    // Cull pairs whose initial separation exceeds the maximum possible
    // relative displacement over the lookahead window.
    double broad_radius = std::min(15.0 * lookahead_s, 2.0 * RE);

    // Position uncertainty grows ~ sqrt(TLE age). Empirical 1-sigma at 1 day: 0.3 km
    double sigma_pos = 0.3 * std::sqrt(std::max(tle_age_days, 0.1));

    // Helper: reconstruct state at arbitrary time t from pre-propagated history.
    // Uses the nearest pre-propagated frame + one RK4 step for the remainder.
    auto state_at_t = [&](const std::vector<double>& history, int n_objects, int obj_idx, double t) -> StateVector {
        int base_step = std::min(static_cast<int64_t>(t / step_s), steps);
        double rem = t - base_step * step_s;
        StateVector s;
        std::memcpy(s.raw(), &history[base_step * (n_objects * 6) + obj_idx * 6], 6 * sizeof(double));
        if (rem > 1e-9) {
            s = prop.propagate(s, rem, 0.0);
        }
        return s;
    };

    // ── 3. Pairwise sweep + Brent refinement ───────────────────────────────
    for (int i = 0; i < ns; ++i) {
        // Broad-phase: sat i initial position
        size_t si = (size_t)i * 6;
        double sx0 = init_sats[si];
        double sy0 = init_sats[si + 1];
        double sz0 = init_sats[si + 2];

        for (int j = 0; j < nd; ++j) {
            size_t dj = (size_t)j * 6;
            double dx0 = sx0 - init_debs[dj];
            double dy0 = sy0 - init_debs[dj + 1];
            double dz0 = sz0 - init_debs[dj + 2];
            if (dx0*dx0 + dy0*dy0 + dz0*dz0 > broad_radius * broad_radius)
                continue;

            // ── Coarse sweep over pre-propagated history ───────────────────
            double min_distance = std::numeric_limits<double>::max();
            double tca_coarse   = 0.0;
            int tca_step        = 0;

            size_t ns6 = (size_t)ns * 6;
            size_t nd6 = (size_t)nd * 6;
            for (int step = 0; step < n_frames; ++step) {
                double* s = &sat_history[(size_t)step * ns6 + si];
                double* d = &deb_history[(size_t)step * nd6 + dj];
                double dx = s[0] - d[0], dy = s[1] - d[1], dz = s[2] - d[2];
                double dist = std::sqrt(dx*dx + dy*dy + dz*dz);

                if (dist < min_distance) {
                    min_distance = dist;
                    tca_coarse   = step * step_s;
                    tca_step     = step;
                }
            }

            if (min_distance >= ADVISORY_DISTANCE) continue;

            // ── Brent refinement ───────────────────────────────────────────
            double t_lo = std::max(0.0, tca_coarse - step_s);
            double t_hi = std::min(lookahead_s, tca_coarse + step_s);

            auto distance_at_t = [&](double t) -> double {
                auto s = state_at_t(sat_history, ns, i, t);
                auto d = state_at_t(deb_history, nd, j, t);
                double dx = s[0]-d[0], dy = s[1]-d[1], dz = s[2]-d[2];
                return std::sqrt(dx*dx + dy*dy + dz*dz);
            };

            double tca_refined = brent_minimise(distance_at_t, t_lo, t_hi, 0.1);
            auto s_tca = state_at_t(sat_history, ns, i, tca_refined);
            auto d_tca = state_at_t(deb_history, nd, j, tca_refined);

            double dx_f = s_tca[0]-d_tca[0];
            double dy_f = s_tca[1]-d_tca[1];
            double dz_f = s_tca[2]-d_tca[2];
            double min_dist_refined = std::sqrt(dx_f*dx_f + dy_f*dy_f + dz_f*dz_f);

            double final_dist = std::min(min_distance, min_dist_refined);
            double final_tca  = (min_dist_refined < min_distance) ? tca_refined : tca_coarse;

            Severity severity = Severity::NONE;
            if      (final_dist < CRITICAL_DISTANCE)  severity = Severity::CRITICAL;
            else if (final_dist < WARNING_DISTANCE)   severity = Severity::WARNING;
            else if (final_dist < ADVISORY_DISTANCE)  severity = Severity::ADVISORY;
            else continue;

            std::array<double, 3> rel_v = {
                s_tca[3] - d_tca[3],
                s_tca[4] - d_tca[4],
                s_tca[5] - d_tca[5]
            };
            double rel_speed = std::sqrt(rel_v[0]*rel_v[0] + rel_v[1]*rel_v[1] + rel_v[2]*rel_v[2]);

            ConjunctionWarning w;
            w.sat_id                   = i;
            w.debris_id                = j;
            w.current_distance         = final_dist;
            w.time_to_closest_approach = final_tca;
            w.severity                 = severity;
            w.relative_velocity        = rel_v;
            w.pc_result                = chan_pc(final_dist, sigma_pos, rel_speed);

            warnings.push_back(w);
        }
    }

    return warnings;
}
