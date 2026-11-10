---
description: 调度、页面置换、银行家算法、PV、CIDR、地址转换、Cache、补码与随堂自测。
---

# 交互练习

修改参数后运行，可逐步查看计算过程。随堂自测提交后显示解析。

| 想练什么 | 课程 | 章节 | 练习入口 | 建议做法 |
| --- | --- | --- | --- | --- |
| 比较执行顺序与周转时间 | [操作系统概论](../courses/operating-systems/index.md) | [第 3 章 进程调度与死锁](../courses/operating-systems/chapter-03.md#s3) | [进程调度](scheduling.md) | 同一组作业切换三种算法 |
| 分清装入次序和最近使用 | [操作系统概论](../courses/operating-systems/index.md) | [第 4 章 内存管理](../courses/operating-systems/chapter-04.md#s10) | [页面置换](paging.md) | 先填页框，再比较缺页数 |
| 区分可分配与安全分配 | [操作系统概论](../courses/operating-systems/index.md) | [第 3 章 进程调度与死锁](../courses/operating-systems/chapter-03.md#s10) | [银行家算法](banker.md) | 先找安全序列，再加资源请求 |
| 追踪许可、等待和唤醒 | [操作系统概论](../courses/operating-systems/index.md) | [第 2 章 进程管理](../courses/operating-systems/chapter-02.md#s10) | [PV 与信号量](semaphore.md) | 先预测队列，再逐个核对原子操作 |
| 计算地址块与路由选择 | [计算机网络技术](../courses/computer-networks/index.md) | [第 5 章 网络互联技术](../courses/computer-networks/chapter-05.md#s5) | [CIDR 地址块](cidr.md) | 手算网络边界，再比较匹配前缀 |
| 分清页号、偏移和物理块 | [操作系统概论](../courses/operating-systems/index.md) | [第 4 章 内存管理](../courses/operating-systems/chapter-04.md#s4) | [地址转换](address.md) | 分别尝试驻留、缺页、越界 |
| 理解同一行的冲突 | [计算机组成原理](../courses/computer-organization/index.md) | [第 5 章 存储器层次结构](../courses/computer-organization/chapter-05.md#s5) | [Cache 映射](cache.md) | 比较同块访问和不同块同一行 |
| 区分截断结果和溢出 | [计算机组成原理](../courses/computer-organization/index.md) | [第 2 章 数据的表示和运算](../courses/computer-organization/chapter-02.md#s7) | [补码加减](complement.md) | 先判断范围，再读位模式 |
| 检查各课程的易错点 | [四门课程](../courses/index.md) | [第 1 章至第 9 章](../courses/index.md) | [随堂自测](quiz.md) | 提交后读解析，最后重练错题 |

计算结果可用“上一步”“下一步”逐步查看，或点击“显示全部步骤”。 页面下方另有算例，供手算后核对。
