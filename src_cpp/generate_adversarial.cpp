#include "generate_adversarial.h"
#include <random>

std::pair<Curve, Curve> generate_adversarial_pair(int n, double r, double D, unsigned seed) {
    std::mt19937 rng(seed);
    std::uniform_real_distribution<double> uni(-r, r);

    auto sample_disk = [&]() -> Point {
        for (;;) {
            double x = uni(rng), y = uni(rng);
            if (x*x + y*y <= r*r) return {x, y};
        }
    };

    Curve c1, c2;
    c1.reserve(n);
    c2.reserve(n);

    for (int i = 0; i < n;   ++i) c1.push_back(sample_disk());
    for (int i = 0; i < n-1; ++i) c2.push_back(sample_disk());
    c2.push_back({D, 0.0});

    return {c1, c2};
}
