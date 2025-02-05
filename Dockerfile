# Image for Blender as a Python module inside of a docker container. Rendering is done using NVIDIA GPUs with either CUDA or OptiX frameworks.
FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

# **********************************************************************************************************
# Change for desired Blender branch and Blender version. Make sure you have the matching Python version for that Blender version
# **********************************************************************************************************
ARG BLENDER_BRANCH="v4.3.2"
ARG BLENDER_VERSION_MAIN=4.3
ARG PYTHON_VERSION=3.11


# Install all required dependencies in a single apt-get command
RUN apt-get update && \
    apt-get install -y --no-install-recommends \ 
    build-essential \
    cmake \
    dkms \
    git \
    git-lfs \
    libdbus-1-dev \
    libegl-dev \
    libgl1-mesa-dev \
    libglfw3-dev \
    libglvnd-dev \
    libopenexr-dev \
    libsm6 \
    libx11-dev \
    libxinerama-dev \
    libxcursor-dev \
    libxi-dev \
    libxkbcommon-dev \
    libxrandr-dev \
    libxxf86vm-dev \
    linux-libc-dev \
    nvidia-cuda-toolkit \
    pkg-config \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    python3-apt \
    python3-distutils \
    python3-pip \
    zlib1g \
    zlib1g-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Make your Python version the default Python3 version
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1

# Clone Blender and update dependencies
RUN mkdir blender_dir && cd blender_dir && \
    git clone https://projects.blender.org/blender/blender.git --single-branch --depth 1 --branch ${BLENDER_BRANCH} \
    && cd /blender_dir/blender/ && ./build_files/utils/make_update.py --use-linux-libraries

# Compile Blender with CUDA 
RUN cd blender_dir/blender && \
    make update && make bpy CC=/usr/lib/nvidia-cuda-toolkit/bin/gcc \
    CPP=/usr/lib/nvidia-cuda-toolkit/bin/g++ \
    CXX=/usr/lib/nvidia-cuda-toolkit/bin/g++ \
    LD=/usr/lib/nvidia-cuda-toolkit/bin/g++ -j$(nproc)


# **********************************************************************************************************
# Copy NVIDIA OptiX SDK. Change to match folder name.
# **********************************************************************************************************
ARG OPTIX_DIR_NAME="NVIDIA-OptiX-SDK-8.0.0-linux64-x86_64"
COPY OPTIX_DIR_NAME /optix

# Build and configure OptiX
RUN ln -fs /usr/lib/nvidia-cuda-toolkit/bin/g++ /usr/bin/g++ && \
    ln -fs /usr/lib/nvidia-cuda-toolkit/bin/gcc /usr/bin/gcc && \
    mkdir /optix/build && cd /optix/build && \
    cmake ../SDK && make -j$(nproc)

# Set environment variables for OptiX system-wide
ENV OPTIX_ROOT=/optix
ENV OPTIX_ROOT_DIR=/optix/
ENV OPTIX_INCLUDE_DIR=$OPTIX_ROOT/include
ENV OPTIX_LIBRARY_DIR=$OPTIX_ROOT/build/lib
ENV OPTIX_BIN_DIR=$OPTIX_ROOT/build/bin
ENV PATH=$OPTIX_BIN_DIR:$PATH
ENV LD_LIBRARY_PATH=$OPTIX_LIBRARY_DIR:$LD_LIBRARY_PATH
ENV CMAKE_PREFIX_PATH=$OPTIX_ROOT:$CMAKE_PREFIX_PATH

# Prepare Blender build directory
RUN mkdir /blender_dir/build
WORKDIR /blender_dir/build

# configure build for blender as a module with OPTIX
RUN cmake -C ../blender/build_files/cmake/config/bpy_module.cmake ../blender \
    -DPYTHON_SITE_PACKAGES=/usr/local/lib/python${PYTHON_VERSION}/site-packages/  \
    -DWITH_PLAYER=OFF -DWITH_PYTHON_MODULE=ON -DWITH_INSTALL_PORTABLE=OFF \
    -DWITH_CYCLES_CUDA_BINARIES=ON \
    -DWITH_CYCLES_DEVICE_CUDA=ON \
    -DWITH_CYCLES_DEVICE_OPTIX=ON \
    -DOPTIX_ROOT_DIR=/optix/

# Compile Blender as a Python module
WORKDIR /blender_dir/blender
RUN make bpy

# Set Python paths
ENV PYTHONPATH="/usr/lib/python${PYTHON_VERSION}/site-packages:$PYTHONPATH"
ENV PYTHONPATH="/usr/local/lib/python${PYTHON_VERSION}/dist-packages:$PYTHONPATH"
ENV PYTHONPATH="/blender_dir/blender/lib/linux_x64/python/lib/python${PYTHON_VERSION}/site-packages/:$PYTHONPATH"
ENV PYTHONPATH="/blender_dir/build_linux_bpy/bin/:$PYTHONPATH"

# Copy requirements.txt and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -f requirements.txt

WORKDIR /root

# Precompile Cycles CUDA kernel
RUN mkdir -p /root/.cache/cycles/kernels

# **********************************************************************************************************
# INSTRUCTIONS TO PRECOMPILE CYCLES CUDA KERNEL:
#
# 1. Build image with the following command commented out
# 2. Run script simple_cube: python3 simple_cube.py
# 3. The script should run a command to precompile Cycles CUDA kernel. Copy that command. It should look similar to the one commented out below
# 4. Paste command. Make sure it is uncommented. Build image again.
# **********************************************************************************************************
# RUN nvcc -arch=$GPU_ARCH --cubin /blender_dir/build_linux_bpy/bin/bpy/${BLENDER_VERSION_MAIN}/scripts/addons_core/cycles/source/kernel/device/cuda/kernel.cu \
# -o /root/.cache/cycles/kernels/cycles_kernel_sm_86_8493A57B417875175D335E518A599773.cubin -m64 --ptxas-options="-v" --use_fast_math -DNVCC \ 
#     -I /blender_dir/build_linux_bpy/bin/bpy/${BLENDER_VERSION_MAIN}/scripts/addons_core/cycles/source -DWITH_NANOVDB
# ***PASTE COMMAND HERE***

WORKDIR /workspace

CMD ["bash"]
