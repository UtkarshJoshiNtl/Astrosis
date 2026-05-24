#!/bin/bash
# Build script for C++/CUDA backends
# This script compiles the high-performance physics engine backends

set -e

echo "Building Astrosis C++/CUDA backends..."

# Check if CMake is installed
if ! command -v cmake &> /dev/null; then
    echo "Error: CMake is not installed. Please install CMake 3.15+"
    exit 1
fi

# Create build directory
mkdir -p cpp/build
cd cpp/build

# Configure with CMake
echo "Configuring with CMake..."
if command -v nvcc &> /dev/null; then
    echo "CUDA detected - enabling CUDA support"
    cmake .. -DCMAKE_BUILD_TYPE=Release -DENABLE_CUDA=ON
else
    echo "CUDA not found - building CPU-only backend"
    cmake .. -DCMAKE_BUILD_TYPE=Release -DENABLE_CUDA=OFF
fi

# Build
echo "Compiling..."
make -j$(nproc)

echo "Build complete!"
echo "Backend libraries are in cpp/build/"
