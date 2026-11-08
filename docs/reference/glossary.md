# 术语与缩写表

OS：操作系统概论；CO：计算机组成原理；CN：计算机网络技术；MM：多媒体技术及应用。

| 术语 | 含义 | 章节 |
| --- | --- | --- |
| OS | 操作系统 | [OS 1](../courses/operating-systems/chapter-01.md) |
| PCB | 进程控制块 | [OS 2](../courses/operating-systems/chapter-02.md#s2) |
| P/V | P 等待、V 发信号 | [OS 2](../courses/operating-systems/chapter-02.md#s10) |
| Mesa | 条件通知后重新竞争锁 | [OS 2](../courses/operating-systems/chapter-02.md#s12) |
| IPC | 进程间通信 | [OS 2](../courses/operating-systems/chapter-02.md#s13) |
| FCFS | 先来先服务 | [OS 3](../courses/operating-systems/chapter-03.md#s4) · [调度实验](../labs/scheduling.md) |
| RR | 时间片轮转 | [OS 3](../courses/operating-systems/chapter-03.md#s4) |
| EDF | 最早截止时间优先 | [OS 3](../courses/operating-systems/chapter-03.md#s5) |
| LLF | 最小松弛度优先 | [OS 3](../courses/operating-systems/chapter-03.md#s5) |
| Need | 最大剩余资源需求 | [OS 3](../courses/operating-systems/chapter-03.md#s10) · [安全性练习](../labs/banker.md) |
| Allocation | 当前已分配资源量 | [OS 3](../courses/operating-systems/chapter-03.md#s10) |
| 页号 / 页内偏移 | 分页地址两段，转换保留偏移 | [OS 4](../courses/operating-systems/chapter-04.md#s4) · [地址转换](../labs/address.md) |
| TLB | 地址转换缓存 | [OS 4](../courses/operating-systems/chapter-04.md#s5) |
| FIFO | 淘汰最早装入的页 | [OS 4](../courses/operating-systems/chapter-04.md#s10) · [置换练习](../labs/paging.md) |
| LRU | 淘汰最久未访问的页 | [OS 4](../courses/operating-systems/chapter-04.md#s10) |
| OPT | 淘汰未来最晚再用的页 | [OS 4](../courses/operating-systems/chapter-04.md#s10) |
| FAT | 文件分配表，记簇链 | [OS 5](../courses/operating-systems/chapter-05.md#s5) |
| i 结点 | 记文件属性与数据位置 | [OS 5](../courses/operating-systems/chapter-05.md#s7) |
| SPOOLing | 磁盘队列暂存设备作业 | [OS 6](../courses/operating-systems/chapter-06.md#s6) |
| PC | 程序计数器，记指令位置 | [CO 1](../courses/computer-organization/chapter-01.md#s4) |
| IR | 暂存当前指令 | [CO 1](../courses/computer-organization/chapter-01.md#s4) |
| ISA | 指令集体系结构，约定机器级行为 | [CO 1](../courses/computer-organization/chapter-01.md#s3) |
| CPI | 每条指令平均时钟周期 | [CO 1](../courses/computer-organization/chapter-01.md#s5) |
| BCD | 十进制逐位编码 | [CO 2](../courses/computer-organization/chapter-02.md#s1) |
| ALU | 算术逻辑单元 | [CO 2](../courses/computer-organization/chapter-02.md#s7) |
| 进位 / 有符号溢出 | 无符号进位 / 带符号越界，判据不同 | [CO 2](../courses/computer-organization/chapter-02.md#s7) · [补码练习](../labs/complement.md) |
| EA | 有效地址，由寻址方式定 | [CO 3](../courses/computer-organization/chapter-03.md#s2) |
| RAW | 先写后读的真依赖，寄存器重命名无效 | [CO 4](../courses/computer-organization/chapter-04.md#s6) |
| SRAM | 静态随机存储器，通电保持 | [CO 5](../courses/computer-organization/chapter-05.md#s2) |
| DRAM | 动态随机存储器，需刷新 | [CO 5](../courses/computer-organization/chapter-05.md#s2) |
| Cache | 高速缓存，按块存主存副本 | [CO 5](../courses/computer-organization/chapter-05.md#s5) · [映射练习](../labs/cache.md) |
| AMAT | 平均存储访问时间 | [CO 5](../courses/computer-organization/chapter-05.md#s5) |
| DMA | 直接存储器访问，设备侧或专用引擎搬运 | [CO 6](../courses/computer-organization/chapter-06.md#s5) |
| IOMMU | I/O 地址转换与设备隔离 | [CO 6](../courses/computer-organization/chapter-06.md#s5) |

## 计算机网络技术

| 术语 | 含义 | 章节 |
| --- | --- | --- |
| LAN / WAN | 局域网 / 广域网，范围与速率无关 | [CN 1](../courses/computer-networks/chapter-01.md#s2) |
| Baud / bit/s | 每秒码元数 / 每秒比特数 | [CN 2](../courses/computer-networks/chapter-02.md#s3) |
| PCM | 抽样、量化、编码，各改一维 | [CN 2](../courses/computer-networks/chapter-02.md#s6) |
| FDM / TDM / WDM / CDM | 按频带、时间、波长、码片复用 | [CN 2](../courses/computer-networks/chapter-02.md#s7) |
| ARQ / FEC | 反馈重传 / 前向纠错 | [CN 2](../courses/computer-networks/chapter-02.md#s8) |
| PDU / SDU / PCI | 本层协议单元 / 上层数据 / 控制信息 | [CN 3](../courses/computer-networks/chapter-03.md#s2) |
| TCP / UDP | 连接可靠 / 无连接报文 | [CN 3](../courses/computer-networks/chapter-03.md#s4) |
| rwnd / cwnd | 接收窗口 / 拥塞窗口 | [CN 3](../courses/computer-networks/chapter-03.md#s6) |
| CSMA/CD / CSMA/CA | 以太网冲突检测 / 无线冲突避免 | [CN 4](../courses/computer-networks/chapter-04.md#s7) |
| MAC / VLAN / Trunk | 链路地址 / 广播域 / 跨交换机承载 | [CN 4](../courses/computer-networks/chapter-04.md#s5) |
| CIDR | 前缀界定地址块，可路由聚合 | [CN 5](../courses/computer-networks/chapter-05.md#s5) |
| NAT | 地址转换与返回映射 | [CN 5](../courses/computer-networks/chapter-05.md#s6) |
| ARP / DHCP | 链路地址解析 / 动态配置分配 | [CN 5](../courses/computer-networks/chapter-05.md#s8) |
| ICMP / IGMP | 差错与查询 / 多播成员关系 | [CN 5](../courses/computer-networks/chapter-05.md#s8) |
| DNS / URL / HTTP | 名字解析 / 资源定位 / 请求响应 | [CN 6](../courses/computer-networks/chapter-06.md#s5) |
| SMTP / POP3 / IMAP | 邮件发送 / 读取 / 管理 | [CN 6](../courses/computer-networks/chapter-06.md#s4) |
| Cookie / Session | 客户端数据 / 服务端会话状态 | [CN 6](../courses/computer-networks/chapter-06.md#s6) |
| SNMP / SMI / MIB | 管理协议 / 对象描述 / 对象库 | [CN 7](../courses/computer-networks/chapter-07.md#s5) |
| OID / Trap | 对象标识 / 代理主动上报 | [CN 7](../courses/computer-networks/chapter-07.md#s5) |
| AD / OU / LDAP | 活动目录 / 组织单位 / 目录访问协议 | [CN 8](../courses/computer-networks/chapter-08.md#s6) |
| IPsec / AH / ESP | 网络层安全：AH 鉴别 / ESP 加密 | [CN 9](../courses/computer-networks/chapter-09.md#s6) |
| CA / KDC | 证书签发 / 密钥分配中心 | [CN 9](../courses/computer-networks/chapter-09.md#s4) |

## 多媒体技术及应用 {#multimedia}

| 术语 | 含义 | 章节 |
| --- | --- | --- |
| 表示媒体 / 存储媒体 | 编码形式 / 保存数据的实体 | [MM 1](../courses/multimedia-technology/chapter-01.md#s1) |
| 实时 / 顺序流式传输 | 按时间送达 / 顺序下载边播放 | [MM 1](../courses/multimedia-technology/chapter-01.md#s5) |
| 输入码 / 内部编码 / 字形 | 输入选择 / 机内表示 / 显示字形 | [MM 3](../courses/multimedia-technology/chapter-03.md#s2) |
| OCR | 页图识别字符，仍需对照原页 | [MM 3](../courses/multimedia-technology/chapter-03.md#s6) |
| 像素尺寸 / ppi / dpi | 像素数、每英寸像素数、每英寸点数 | [MM 4](../courses/multimedia-technology/chapter-04.md#s2) |
| 位深 / 像素数据量 | 每像素位数 / 未压缩总字节 | [MM 4](../courses/multimedia-technology/chapter-04.md#s5) |
| 采样 / 量化 / 编码 | 时间取样 / 幅值离散 / 二进制表示 | [MM 5](../courses/multimedia-technology/chapter-05.md#s2) |
| PCM 数据量 | 未压缩采样字节，需采样率等四参数 | [MM 5](../courses/multimedia-technology/chapter-05.md#s3) |
| MIDI | 演奏消息，不含波形采样 | [MM 5](../courses/multimedia-technology/chapter-05.md#s4) |
| 制式 / 编码 / 文件格式 | 信号组织 / 压缩方法 / 文件封装 | [MM 6](../courses/multimedia-technology/chapter-06.md#s3) |
| 工程 / 输出 | 剪辑工程 / 交付成品 | [MM 6](../courses/multimedia-technology/chapter-06.md#s4) |
| 普通帧 / 关键帧 / 空白关键帧 | 延续 / 定义画面 / 清空一段 | [MM 7](../courses/multimedia-technology/chapter-07.md#s5) |
| 动作补间 / 形状补间 | 属性变化 / 轮廓变形 | [MM 7](../courses/multimedia-technology/chapter-07.md#s6) |
| 文档相对路径 | 相对当前文档目录 | [MM 8](../courses/multimedia-technology/chapter-08.md#s4) |
| 导航图 / 屏幕脚本 | 内容关系与跳转 / 各屏要素 | [MM 9](../courses/multimedia-technology/chapter-09.md#s5) |
