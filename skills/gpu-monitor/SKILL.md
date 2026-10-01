# GPU 监控技能

用于采集 Brown 实验室 A100/H100 GPU 节点的显存、利用率、温度、功率和异常状态。

## 适用场景

- 用户询问“哪台服务器空闲”
- 用户要求检查 GPU 使用率
- 用户要求追踪高显存 PID
- 用户要求诊断 OOM、Xid、ECC、NVRM 错误

## 推荐命令

```bash
nvidia-smi
nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw --format=csv,noheader,nounits
nvidia-smi pmon -c 1
nvidia-smi dmon -c 1
```

## 重点指标

- GPU 显存使用率
- GPU 利用率
- GPU 温度
- GPU 功率
- 进程 PID、用户名、显存占用
- Xid、ECC、NVRM 错误

## 判断规则

- 显存占用高但 GPU 利用率长期接近 0，标记为疑似空占显存。
- 温度超过 80C 标记 warning，超过 88C 标记 critical。
- 出现 Xid/ECC/NVRM 错误时至少标记 warning，重复出现时标记 critical。
- 训练进程 OOM 后应追踪 PID、用户、命令和近期日志证据。

## 输出要求

输出结构化摘要，至少包含：

- 节点名
- GPU 编号
- 状态 normal / warning / critical
- 指标摘要
- 异常证据
- 建议动作
