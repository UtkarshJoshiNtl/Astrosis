#pragma once
#include <string>
#include <vector>
#include <array>
#include "propagator.h"
#include "physics_constants.h"

// Probability of Collision result via Chan's method
struct PcResult {
    double pc;              // collision probability [0,1]
    double sigma_pos_km;    // 1-sigma combined position uncertainty [km]
    bool   computed;        // false if inputs were degenerate
};

enum class Severity { NONE, ADVISORY, WARNING, CRITICAL };

inline std::string severity_to_string(Severity s) {
    switch (s) {
        case Severity::CRITICAL:  return "CRITICAL";
        case Severity::WARNING:   return "WARNING";
        case Severity::ADVISORY:  return "ADVISORY";
        case Severity::NONE:      return "NONE";
    }
    return "NONE";
}

struct ConjunctionWarning {
    int sat_id;
    int debris_id;
    double current_distance;            // km at TCA
    double time_to_closest_approach;    // s (Brent-refined)
    Severity severity;                  // severity level
    std::array<double, 3> relative_velocity;  // km/s at TCA
    PcResult pc_result;

    ConjunctionWarning()
        : sat_id(0), debris_id(0), current_distance(0.0),
          time_to_closest_approach(0.0), severity(Severity::NONE),
          relative_velocity{0, 0, 0},
          pc_result{0.0, 0.0, false} {}
};

class ConjunctionDetector {
public:
    ConjunctionDetector();

    std::vector<ConjunctionWarning> detect(
        const std::vector<StateVector>& sat_states,
        const std::vector<StateVector>& debris_states,
        double lookahead_s = 86400.0,
        double step_s = 60.0,
        double tle_age_days = 1.0  // used for covariance estimation
    ) const;
};
