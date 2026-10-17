# 小米 AX3000T 固件编译

本仓库基于 [padavanonly/immortalwrt-mt798x-6.6](https://github.com/padavanonly/immortalwrt-mt798x-6.6)，仅维护小米 AX3000T 原厂分区布局的编译配置。

## 编译配置

- 唯一预设：[`defconfig/mt7981-ax3000t.config`](defconfig/mt7981-ax3000t.config)。
- 平台：MediaTek Filogic / MT7981，Linux 6.6 系列内核。
- 设备：`xiaomi_mi-router-ax3000t`，原厂分区布局。
- 无线：联发科 `mt_wifi` 厂商驱动及 `mtwifi-cfg` 管理组件。
- 包含中文版 PassWall，使用 Xray 核心。
- 不包含 Samba4 文件共享、网络唤醒和 WireGuard。
- 开启 initramfs，同时生成首次迁移镜像和后续升级镜像。

其他机型的预设配置已删除。保留上游的构建系统、软件包和底层平台源码，实际编译仅选择 AX3000T。

## GitHub Actions 编译

1. 打开本仓库的 **Actions** 页面。
2. 选择 **Build AX3000T Firmware**。
3. 点击 **Run workflow**，使用 `openwrt-24.10-6.6` 分支。
4. 编译成功后，下载 **xiaomi-ax3000t-firmware** 产物。

工作流从唯一预设生成 `.config`，并检查设备选择、厂商无线驱动、PassWall 和 Xray 是否包含、Samba4 等已移除功能是否禁用，以及首次迁移镜像是否生成。

产物包括：

- `*xiaomi_mi-router-ax3000t-initramfs-factory.ubi`：首次迁移流程所需镜像。
- `*xiaomi_mi-router-ax3000t-squashfs-sysupgrade.bin`：对应布局下的系统升级镜像。
- AX3000T 的其他生成文件、校验信息及构建信息。
- `ax3000t.build.config`：编译实际使用的完整配置。

这些镜像针对原厂分区布局。使用 MTK U-Boot 或 OpenWrt U-Boot 改版分区的设备不属于当前配置目标；首次迁移镜像也不是小米官方网页升级包。

## 本地编译

使用安装好构建依赖的 Linux 环境，依赖列表可参考[编译工作流](.github/workflows/build-ax3000t.yml)。源码目录需位于区分大小写的文件系统中，路径不含空格或中文。

```bash
git clone --depth 1 --branch openwrt-24.10-6.6 https://github.com/JIANCXG/237.git ax3000t
cd ax3000t
./scripts/feeds update -a
./scripts/feeds install -a
cp defconfig/mt7981-ax3000t.config .config
make defconfig
make download -j2
make -j2 V=s
```

固件输出目录：`bin/targets/mediatek/filogic/`。

## 上游与许可

- [ImmortalWrt](https://github.com/immortalwrt/immortalwrt)
- [padavanonly/immortalwrt-mt798x-6.6](https://github.com/padavanonly/immortalwrt-mt798x-6.6)
- 保留上游许可证与版权声明，详见 [COPYING](COPYING) 和 [LICENSES](LICENSES)。
