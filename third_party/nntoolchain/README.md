**注意：所有提交到代码库的第三方依赖库都必须是release版本的**

## TPU1684 2023-11-20
sha256: c776c59dbede5986950da12c9c294ae0da06057b

``` bash
cd  nntoolchain/net_compiler/
source  scripts/envsetup.sh
**debug: rebuild_bm1684_backend_cmodel**
**release: rebuild_bm1684_backend_release_cmodel**
cp out/install/lib/libcmodel_1684.so /workspace/tpu-mlir/third_party/nntoolchain/lib/
cp bmcompiler/libbackend/libbackend_1684.so /workspace/tpu-mlir/third_party/nntoolchain/lib/
```

## TPU1686 2023-11-20
sha256: 93d5aea2aaf94d3efad69649a6ed0be348be1c9f

``` bash
#bm1684x
cd TPU1686
source  scripts/envsetup.sh bm1684x
**debug: rebuild_backend_lib_cmodel**
**release: unset EXTRA_CONFIG && rebuild_backend_lib_release_cmodel**
cp build/backend_api/libbackend_bm1684x.so  /workspace/tpu-mlir/third_party/nntoolchain/lib/libbackend_1684x.so
cp build_runtime/firmware_core/libcmodel_firmware.so  /workspace/tpu-mlir/third_party/nntoolchain/lib/libcmodel_1684x.so
rebuild_firmware
cp build/firmware_core/libfirmware_core.so /workspace/tpu-mlir/third_party/nntoolchain/lib/libbm1684x_kernel_module.so

#bm1686
cd TPU1686
source  scripts/envsetup.sh bm1686
**debug: rebuild_backend_lib_cmodel**
**release: unset EXTRA_CONFIG && rebuild_backend_lib_release_cmodel**
cp build/backend_api/libbackend_bm1686.so  /workspace/tpu-mlir/third_party/nntoolchain/lib/libbackend_1688.so
cp build_runtime/firmware_core/libcmodel_firmware.so  /workspace/tpu-mlir/third_party/nntoolchain/lib/libcmodel_1688.so

#sg2260
cd TPU1686
source  scripts/envsetup.sh sg2260
**debug: rebuild_backend_lib_cmodel**
**release: unset EXTRA_CONFIG && rebuild_backend_lib_release_cmodel**
cp build/backend_api/libbackend_sg2260.so /workspace/tpu-mlir/third_party/nntoolchain/lib/libbackend_sg2260.so
cp build_runtime/firmware_core/libcmodel_firmware.so /workspace/tpu-mlir/third_party/nntoolchain/lib/libcmodel_sg2260.so

```bash
pushd nntoolchain/TPU1686/
source scripts/envsetup.sh
rebuild_firmware
cp build/firmware_core/libfirmware_core.so /workspace/tpu-mlir/third_party/nntoolchain/lib/libbm1684x_kernel_module.so
popd
```


## tpu-runtime 2023-09-18
build from tpu-runtime 969fb471519b9c2cf34398d914e69f27786e8f52
``` bash
pushd libsophon
mkdir -p build && cd build
cmake -G Ninja -DPLATFORM=cmode ..
ninja
cp tpu-runtime/libbmrt.so* /workspace/tpu-mlir/third_party/nntoolchain/lib/
cp bmlib/libbmlib.so* /workspace/tpu-mlir/third_party/nntoolchain/lib/
popd
```


## tpu-cpuop 2023-10-10

```bash
pushd /workspace/nntoolchain/net_compiler
source new_scripts/envsetup.sh
rebuild_cpuop
cp /workspace/nntoolchain/net_compiler/out/lib/libcpuop.so* /workspace/tpu-mlir/third_party/nntoolchain/lib/

# libbmcpu.so/libusercpu.so are deprecated
```
