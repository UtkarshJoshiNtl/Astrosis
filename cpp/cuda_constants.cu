/*
 * cpp/cuda_constants.cu — Single source of truth for __constant__ variables
 * ========================================================================
 * Declared extern in cuda_physics.cuh; defined here exactly once.
 * NOTE: Do NOT include cuda_physics.cuh here — extern declarations would
 * conflict with the actual definitions in the same translation unit.
 */
#include <cuda_runtime.h>

struct CA { double alt, H, rho0; };

__constant__ double C_MU=398600.4418, C_RE=6378.137;
__constant__ double C_J2=1.08263e-3, C_J3=-2.53266e-6, C_J4=-1.61990e-6;
__constant__ double C_OMEGA=7.2921150e-5;
__constant__ double C_MU_SUN=132712440018.0, C_MU_MOON=4902.800066;
__constant__ double C_AU=149597870.7, C_P_SR=4.56e-6;
__constant__ CA C_ATM[28]={
    {0,8.44,1.225},{25,6.49,3.899e-2},{30,6.75,1.774e-2},{40,7.58,3.972e-3},
    {50,8.55,1.057e-3},{60,7.71,3.206e-4},{70,6.55,8.770e-5},{80,5.79,1.905e-5},
    {90,5.57,3.396e-6},{100,5.90,5.297e-7},{110,7.17,9.661e-8},{120,9.59,2.438e-8},
    {130,12.2,8.484e-9},{140,15.5,3.845e-9},{150,19.3,2.070e-9},{180,26.0,5.464e-10},
    {200,26.0,2.789e-10},{250,38.5,7.248e-11},{300,51.0,2.418e-11},{350,59.5,9.518e-12},
    {400,67.6,3.725e-12},{450,76.0,1.585e-12},{500,84.0,6.967e-13},{600,105.0,1.454e-13},
    {700,130.0,3.614e-14},{800,180.0,1.170e-14},{900,268.0,5.245e-15},{1000,1e9,3.019e-15}
};
