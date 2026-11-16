---
description: 输入资源向量与矩阵，逐步检查安全序列和试分配后的状态。
---

# 银行家算法练习

[操作系统概论](../courses/operating-systems/index.md) · [第 3 章 进程调度与死锁](../courses/operating-systems/chapter-03.md#s10)
{: .lab-course }

输入 Available、Allocation 和 Max 即可检查安全序列；再加一个请求，可看试分配后是否仍安全。

<div class="study-lab" data-study-lab="banker"><p>正在载入练习；若长时间未出现操作区，请刷新页面。</p></div>
<noscript>本练习需要 JavaScript。可手算：资源池：Available 为 1 1；Allocation 各行为 1 0、0 1、1 0；Max 各行为 2 1、2 1、1 2。</noscript>

## 模型约定

Work 只是安全性检查里的临时向量，并不真的发放资源。找到 Need 各项都不超过 Work 的进程后，假设它完成，把它占有的资源加回 Work。查找按进程编号从小到大，每完成一个就重新扫描一遍。给出的是其中一条可行序列，未必唯一。

一个请求要先过两关：不超过 Need、不超过 Available，才能试分配。试分配后若变成不安全状态，就要拒绝；但**不安全不等于已经死锁**。每次运行都从输入的原状态起算，不会沿用上次的试分配。

默认资源池有 P0、P1、P2 和两类资源。把 P0 的请求设为 `1 0`，再把请求进程改成 P1、请求不变，比较两次试分配后是否安全。

## 算例：安全序列与不安全请求

默认 Available=(1,1)，每个数表示对应类别的资源实例数。按分量相减计算 Need：

| 进程 | Allocation | Max | Need |
| --- | --- | --- | --- |
| P0 | (1,0) | (2,1) | (1,1) |
| P1 | (0,1) | (2,1) | (2,0) |
| P2 | (1,0) | (1,2) | (0,2) |

初始 Work=(1,1)。P0 的 Need 可满足，假设其完成并归还 Allocation，Work 变为 (2,1)；接着 P1 完成，Work 变为 (2,2)；最后 P2 完成，Work=(3,2)。因此 **P0 → P1 → P2** 是一条安全序列。

若从原状态试分配 P1 的请求 (1,0)，Work 变为 (0,1)，三个进程的剩余需求依次是 (1,1)、(1,0)、(0,2)，没有一个逐分量不超过 Work。安全检查无法完成，应撤销此次试分配。它表示不能保证各进程都取得其声明的最大需求，**不能据此判定当前已经死锁**。定义见[安全性](../courses/operating-systems/chapter-03.md#s9)。请求检查见[银行家算法](../courses/operating-systems/chapter-03.md#s10)。

[回看调度与死锁](../courses/operating-systems/chapter-03.md) · [全部交互练习](index.md)
