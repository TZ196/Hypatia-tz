## 目录结构

`my_experiments/` 被划分为共享资源区（shared assets）和各实验独立的工作区。

* `shared/`：可重用的输入、流量生成器以及星座（constellation）定义
* `experiments/`：每个实验一个独立目录，包含脚本、生成的数据、日志和输出文件

## 共享资源

* `shared/input_data/`：通用的地面站输入文件
* `shared/traffic/`：可重用的流量矩阵生成代码
* `shared/constellation/`：可重用的星座定义以及共享的 `MainHelper`
* 直接运行 `shared/constellation/main_*.py` 时，默认输出到 `experiments/<BASE_NAME>/gen_data/`

## 实验工作区

每个实验应当集中存放其专属文件：

* 步骤脚本存放在实验根目录或 `scripts/` 下
* 生成的星座数据存放在 `gen_data/` 下
* ns-3 运行目录存放在 `runs/` 下
* 日志存放在 `logs/` 下
* 笔记与摘要存放在 `notes/` 下
