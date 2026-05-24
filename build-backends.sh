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

# Install pybind11 if not available
if ! python3 -c "import pybind11" 2>/dev/null; then
    echo "Installing pybind11..."
    pip3 install pybind11 --user || {
        echo "Error: Failed to install pybind11. Try: pip3 install pybind11"
        exit 1
    }
fi

# Create build directory
mkdir -p cpp/build
cd cpp/build

# Configure with CMake
echo "Configuring with CMake..."
PYBIND11_DIR=$(python3 -m pybind11 --cmakedir 2>/dev/null || echo "")
CMAKE_ARGS="-DCMAKE_BUILD_TYPE=Release"
if [ -n "$PYBIND11_DIR" ]; then
    CMAKE_ARGS="$CMAKE_ARGS -Dpybind11_DIR=$PYBIND11_DIR"
fi
if command -v nvcc &> /dev/null; then
    echo "CUDA detected - enabling CUDA support"
    cmake .. $CMAKE_ARGS -DUSE_CUDA=ON
else
    echo "CUDA not found - building CPU-only backend"
    cmake .. $CMAKE_ARGS -DUSE_CUDA=OFF
fi

# Build
echo "Compiling..."
make -j$(nproc)

echo "Build complete!"
echo "Backend libraries are in cpp/build/"
