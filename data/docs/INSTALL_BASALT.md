# Installing BASALT on macOS

## Step 1: Install Dependencies

Run the installation script to install all required dependencies via Homebrew:

```bash
cd /Users/rohin/Desktop/code/treehacks-26/data/basalt
./scripts/install_mac_os_deps.sh
```

Or manually install:

```bash
brew install boost opencv cmake pkgconfig lz4 clang-format tbb glew eigen ccache fmt llvm
```

## Step 2: Initialize Git Submodules

The BASALT repository uses submodules that need to be initialized:

```bash
cd /Users/rohin/Desktop/code/treehacks-26/data/basalt
git submodule update --init --recursive
```

## Step 3: Build BASALT

Before compiling on recent AppleClang, apply a small compatibility patch:

```bash
cd /Users/rohin/Desktop/code/treehacks-26/data/basalt
python3 - <<'PY'
from pathlib import Path
files = [
    Path("src/linearization/linearization_abs_qr.cpp"),
    Path("src/linearization/linearization_abs_sc.cpp"),
    Path("src/linearization/linearization_rel_sc.cpp"),
]
for p in files:
    s = p.read_text()
    s = s.replace("Q2Jp.template block(", "Q2Jp.block(")
    s = s.replace("Q2r.template segment(", "Q2r.segment(")
    p.write_text(s)
    print("patched", p)
PY
```

Then create a build directory and compile:

```bash
cd /Users/rohin/Desktop/code/treehacks-26/data/basalt
mkdir -p build
cd build
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DCMAKE_CXX_FLAGS='-Wno-error' \
  -DCMAKE_C_COMPILER_LAUNCHER= -DCMAKE_CXX_COMPILER_LAUNCHER=
make -j8
```

The `-j8` flag uses 8 parallel jobs for faster compilation. Adjust based on your CPU cores.

## Step 4: Install (Optional)

To install BASALT system-wide (so you can run `basalt_vio` from anywhere):

```bash
sudo make install
```

This will install to `/usr/local/bin/` by default. You may need to add `/usr/local/bin` to your PATH if it's not already there.

## Step 5: Verify Installation

After building, you can run BASALT directly from the build directory:

```bash
# From the build directory
./basalt_vio --help
```

Or if installed system-wide:

```bash
basalt_vio --help
```

## Troubleshooting

### If submodules fail to initialize:
```bash
cd /Users/rohin/Desktop/code/treehacks-26/data/basalt
git submodule sync
git submodule update --init --recursive
```

### If cmake fails:
- Make sure all dependencies are installed: `brew list | grep -E "(boost|opencv|cmake|eigen|tbb)"`
- Try cleaning the build directory: `rm -rf build && mkdir build`

### If compilation fails:
- Check that you have the latest Xcode command line tools: `xcode-select --install`
- Make sure you're using a compatible compiler (clang from Xcode or LLVM)
- On recent AppleClang, disable warning-as-error at configure time: `-DCMAKE_CXX_FLAGS='-Wno-error'`
- If ccache causes permission issues, disable launchers: `-DCMAKE_C_COMPILER_LAUNCHER= -DCMAKE_CXX_COMPILER_LAUNCHER=`
- If you see `a template argument list is expected after a name prefixed by the template keyword`, apply the Python patch in Step 3.

## Quick Install Script

You can also run all steps at once:

```bash
cd /Users/rohin/Desktop/code/treehacks-26/data/basalt

# Install dependencies
./scripts/install_mac_os_deps.sh

# Initialize submodules
git submodule update --init --recursive

# AppleClang compatibility patch
python3 - <<'PY'
from pathlib import Path
files = [
    Path("src/linearization/linearization_abs_qr.cpp"),
    Path("src/linearization/linearization_abs_sc.cpp"),
    Path("src/linearization/linearization_rel_sc.cpp"),
]
for p in files:
    s = p.read_text()
    s = s.replace("Q2Jp.template block(", "Q2Jp.block(")
    s = s.replace("Q2r.template segment(", "Q2r.segment(")
    p.write_text(s)
    print("patched", p)
PY

# Build
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DCMAKE_CXX_FLAGS='-Wno-error' \
  -DCMAKE_C_COMPILER_LAUNCHER= -DCMAKE_CXX_COMPILER_LAUNCHER=
make -j8

# Optional: Install
sudo make install
```

