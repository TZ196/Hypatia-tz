# Hypatia 仿真框架文档

LEO 卫星网络仿真框架，四大模块：satgenpy（星座生成）、ns3-sat-sim（包级仿真）、satviz（可视化）、paper（论文复现）。

## 文档目录

| 文件 | 内容 |
|------|------|
| [01-environment.md](01-environment.md) | 环境信息、激活流程、目录总览 |
| [02-framework-data.md](02-framework-data.md) | 星座参数、ISL 配置、地面站数据、路由算法 |
| [03-simulation-pipeline.md](03-simulation-pipeline.md) | 仿真 4 步流水线 + 快速示例 |
| [04-api-reference.md](04-api-reference.md) | satgenpy API 速查 |
| [05-troubleshooting.md](05-troubleshooting.md) | 故障排除 + 安全红线 |
| [06-traffic-simulation-guide.md](06-traffic-simulation-guide.md) | 流量注入、路由修改、地面站映射、Handover 说明 |

核心设计架构
Hypatia 并不是从零开发一个完整的离散事件仿真器，而是将天体动力学计算与经典网络仿真器（ns-3）有机结合。它主要由以下四个核心组件构成：

satgenpy（状态生成模块）： 这是一个基于 Python 的核心模块。它利用天体动力学库（如 sgp4、astropy、ephem 等）计算低轨卫星在特定时间段内的轨道运行轨迹，并基于地理位置动态计算地面站（GS）与卫星、以及卫星与卫星之间（ISL，星间链路）的可见性和连接性。最终，它会预先计算并输出一个“随时间变化的拓扑和路由状态表”。

ns3-sat-sim（数据包级仿真模块）： 这是基于知名网络模拟器 ns-3 开发的模块。它读取 satgenpy 生成的动态拓扑状态，在 ns-3 中实现端到端的数据包级（Packet-level）网络仿真。它支持评估传输层协议（如 TCP/UDP）、拥塞控制算法、星间路由协议的实际性能。

可视化模块（基于 Cesium）： Hypatia 提供了基于 Cesium（开源三维地球可视化框架）的可视化工具。它可以将复杂的卫星轨道、星间链路（ISL）的动态切换、端到端数据传输路径、以及网络流量热点（Hotspots）在 3D 地球模型上直观地渲染出来。

paper 模块： 包含了论文中用于复现其实验和图表的原始代码和绘图脚本（主要使用 gnuplot），也是用户上手使用 Hypatia 的最佳官方教程。