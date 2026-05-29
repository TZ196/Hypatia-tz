## 目录结构

`my_experiments/` 被划分为共享资源区（shared assets）和各实验独立的工作区。

* `shared/`：可重用的输入、流量生成器以及星座（constellation）定义
* `experiments/`：每个实验一个独立目录，包含脚本、生成的数据、日志和输出文件

## 共享资源

* `shared/input_data/`：通用的地面站输入文件
* `shared/traffic/`：可重用的仿真流量计划生成代码，按地面站时区活跃度分配总流量预算，输出 `schedule.csv`、OD 总流量矩阵和地面站活跃度表
* `shared/constellation/`：可重用的星座定义以及共享的 `MainHelper`
* `shared/experiment_pipeline.py`：通用实验流水线，负责地面站定义、流量设计、satgenpy 状态生成、ns-3 运行目录生成和 ns-3 运行
* `shared/tensor_tools.py`：通用张量构建工具，负责从实验输出生成 traffic、RTT、卫星连接张量
* 直接运行 `shared/constellation/main_*.py` 时，默认输出到 `experiments/<BASE_NAME>/gen_data/`

## 实验工作区

每个实验应当集中存放其专属文件：

* 步骤脚本存放在实验根目录或 `scripts/` 下
* 实验输入定义存放在 `input/` 下，例如地面站清单和流量调度
* 生成的星座数据存放在 `gen_data/` 下
* ns-3 运行目录存放在 `runs/` 下
* 日志存放在 `logs/` 下
* 笔记与摘要存放在 `notes/` 下

## 推荐流水线

通用步骤只维护在 `shared/experiment_pipeline.py`。每个实验目录只提供自己的 `experiment_config.py` 和一个调用脚本，例如：

```bash
python run_pipeline.py --threads 4
```

`experiments/iridium_top50_60s/` 和 `experiments/iridium_top30_10s/` 是当前隔离实验示例。后续新实验应新建自己的 `experiments/<experiment_name>/`，只放该实验的配置和调用脚本；运行时生成的 `input/`、`gen_data/`、`runs/`、`logs/` 也只属于该实验。

## 通用张量工具

后处理张量脚本不放在单个实验目录里，统一通过 `tensor_cli.py` 调用：

```bash
python tensor_cli.py iridium_top50_60s traffic --time-slice-s 5
python tensor_cli.py iridium_top50_60s rtt --time-slice-s 5
python tensor_cli.py iridium_top50_60s sat-connectivity --bin-ms 1000
python tensor_cli.py iridium_top50_60s sat-path-flow
```

同样地，`iridium_top30_10s` 的调用方法一致，只需要把实验名替换为 `iridium_top30_10s`。
