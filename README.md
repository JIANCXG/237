# 小米 AX3000T MTK U-Boot 112M 大分区固件编译

本仓库基于 [padavanonly/immortalwrt-mt798x-6.6](https://github.com/padavanonly/immortalwrt-mt798x-6.6)，仅维护小米 AX3000T MTK U-Boot（`mtkuboot`）112M 大分区布局的编译配置。

## 编译配置

- 唯一预设：[`defconfig/mt7981-ax3000t.config`](defconfig/mt7981-ax3000t.config)。
- 平台：MediaTek Filogic / MT7981，Linux 6.6 系列内核。
- 设备：`xiaomi_mi-router-ax3000t-mtkuboot`，MTK U-Boot 112M 大分区布局。
- 分区：UBI 从 `0x600000` 开始，大小为 `0x7000000`（112 MiB）；内核与根文件系统位于同一个 UBI 分区，112M 并非刷入后的剩余可用空间。
- 无线：联发科 `mt_wifi` 厂商驱动及 `mtwifi-cfg` 管理组件。
- LuCI HTTPS：统一使用 OpenSSL 后端。
- 包含官方最新版中文版 PassWall、Xray 与 Sing-box 双核心及 SmartDNS；PassWall、基础软件源及 Go 工具链的上游提交统一固定在 `feeds.conf.default` 与 `.github/passwall-upstream.json`。Sing-box 启用 QUIC 和 uTLS 支持。
- 不包含 Samba4 文件共享、网络唤醒和 WireGuard。
- 保留 initramfs，同时生成 MTK U-Boot 布局的 `factory.bin` 刷入镜像和 `sysupgrade.bin` 升级镜像。

其他机型的预设配置已删除。保留上游的构建系统、软件包和底层平台源码，实际编译仅选择 AX3000T。

## GitHub Actions 编译

1. 打开本仓库的 **Actions** 页面。
2. 选择 **Build AX3000T MTK U-Boot 112M Firmware**。
3. 点击 **Run workflow**，使用 `openwrt-24.10-6.6` 分支。
4. 编译并校验成功后，`publish` 任务自动创建 **Release** 并上传固件，标题标注 **MTK U-Boot 112M 大分区**；到仓库的 **Releases** 页面下载附件。Actions 中同时保留 **xiaomi-ax3000t-mtkuboot-112m-firmware** 产物 30 天。

流程与 `JIANCXG/hanwckf` 一致：检查上游 → 编译校验 → 发布 Release → 记录成功版本。每次发布使用 `ax3000t-passwall-运行ID-尝试次数` 唯一标签，发布说明记录精确源码提交及 PassWall、依赖包和 Go 工具链版本。固件、软件包清单、构建配置和上游版本文件平铺上传，并附带覆盖全部附件的 `sha256sums`。

工作流从唯一预设生成 `.config`，并检查 mtkuboot 设备选择、厂商无线驱动、PassWall、Xray 与 Sing-box 是否包含、Samba4 等已移除功能是否禁用，以及该布局的 factory 和 sysupgrade 镜像是否生成。

## PassWall 自动更新

`Check PassWall updates every 3 days` 工作流每隔至少 72 小时检查官方 PassWall、配套依赖包、Go 1.27 工具链，以及 packages、luci、routing、telephony 四个基础软件源的上游提交。与 `hanwckf` 相同，GitHub 每小时第 17 分钟唤醒工作流，未满 72 小时跳过上游查询；此方式保证跨月时不会缩短检查间隔，实际执行可能受 GitHub 调度延迟影响。

全部上游查询成功后，如发现任一上游有新提交，则统一更新固定版本、提交到当前默认分支并编译发布固件；与上次成功发布的源码、配置及固定版本相同时不编译。仅在 Release 发布成功后更新 `.github/ax3000t-last-success.json`，检查时间不作为编译成功标记。检查失败不推进时间，下次唤醒时重试；编译或发布失败则保持待构建状态，下次每小时唤醒时使用固定版本重试。也可在 Actions 重新运行失败任务，或手动运行检查工作流并勾选 `build` 强制编译。手动检查会绕过 72 小时间隔。修改工作流、构建脚本、AX3000T 配置或 feeds 时也会触发检查与构建。此流程不会自动刷写路由器。

所有软件源均使用精确提交构建，基础软件源的上游变更也参与构建指纹判断。编译阶段只使用固定版本，不再随分支头漂移；这保证源码依赖版本可追溯，但不承诺固件逐字节可复现。

Go 工具链使用 `sbwml/packages_lang_golang` 的 `27.x` 分支（固定提交），替代 OpenWrt 24.10 软件源中的旧 Go 1.23，以满足新版 Xray 的编译要求。

产物包括：

- `*xiaomi_mi-router-ax3000t-mtkuboot-squashfs-factory.bin`：匹配 MTK U-Boot 112M 大分区布局的刷入镜像。
- `*xiaomi_mi-router-ax3000t-mtkuboot-squashfs-sysupgrade.bin`：该布局下的系统升级镜像。
- AX3000T 的其他生成文件、校验信息及构建信息。
- `ax3000t.build.config`：编译实际使用的完整配置。
- `passwall-upstream.json`：PassWall、依赖包和 Go 工具链的固定提交及最近检查时间。

这些镜像仅适用于 MTK U-Boot（`mtkuboot`）112M 大分区布局，不适用于原厂布局或 OpenWrt U-Boot（`ubootmod`）布局。原厂设备需要先按对应教程完成引导与布局迁移，不能直接把此固件当作原厂布局升级包；`factory.bin` 也不是小米官方网页升级包。

历史 Release 可能仍是原厂布局，请以每次发布说明及固件文件名中的 `mtkuboot` 标识为准。

## 本地编译

使用安装好构建依赖的 Linux 环境，依赖列表可参考[编译工作流](.github/workflows/build-ax3000t.yml)。源码目录需位于区分大小写的文件系统中，路径不含空格或中文。

```bash
git clone --depth 1 --branch openwrt-24.10-6.6 https://github.com/JIANCXG/237.git ax3000t
cd ax3000t
bash scripts/prepare-passwall.sh
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
