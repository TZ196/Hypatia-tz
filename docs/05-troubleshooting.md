# 5. 故障排除与安全红线

## 故障排除

| 症状 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError: No module named 'imp'` | Conda Python 3.13 | `conda deactivate`，使用系统 Python |
| `CXXABI_1.3.8 not found` | GCC 版本混用 | `export CC=gcc-9 CXX=g++-9` |
| `program 'sat-sim' not found` | 程序名错误 | 正确名称是 `main_satnet` |
| `.waf3-...` imp 错误 | waf 检测到 Conda Python | 清理 PATH 确保 `/usr/bin/python3` 在前 |
| cartopy import 失败 | 缺少 proj/geos 库 | `apt install libproj-dev proj-data proj-bin libgeos-dev` |
| `Needed a single revision` | submodule 残缺 | `rm -rf <path> .git/modules/<name> && git submodule update --init` |

## 安全红线

以下操作**任何时候不得执行**：

1. 不修改 `/usr/bin/python3` 的 symlink 指向
2. 不修改 `/usr/bin/gcc` 的 symlink 指向
3. 不使用 `update-alternatives` 切换默认编译器
4. 不卸载系统自带 `libstdc++`
5. 不将 `venv/bin` 加入 `~/.bashrc` 的 `PATH`
6. 不使用 `sudo pip install`
7. 不在 root 用户下运行仿真
8. 所有系统级变更保留 `apt remove` 回滚路径
