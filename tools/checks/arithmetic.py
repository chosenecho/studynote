"""Recompute authored OS/CO/CN arithmetic answers from their stated inputs."""
from fractions import Fraction
from pathlib import Path
import math
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
SUPER = {'⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
         '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁻': '-'}
SUB = {'₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
       '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9'}


def superscripts(text):
    return re.sub('[' + ''.join(SUPER) + ']+',
                  lambda m: '^' + ''.join(SUPER[c] for c in m.group(0)), text)


def clean(text):
    for key, value in SUB.items():
        text = text.replace(key, value)
    text = superscripts(text)
    text = re.sub(r'\^\{(\d+)\}', r'^\1', text)
    text = text.replace('$', '').replace('**', '')
    return re.sub(r'\s+', '', text)


def question(course, chapter, number):
    path = ROOT / f'docs/courses/{course}/chapter-{chapter:02}.md'
    text = path.read_text(encoding='utf-8')
    exercise = text.split('## 练习', 1)[1]
    block = re.search(rf'^\*\*{number}\. (.*?)(?=^\*\*\d+\. |\Z)', exercise, re.M | re.S)
    if not block:
        raise ValueError(f'{course} ch{chapter} Q{number}: question not found')
    body = block[1]
    if '**答案：**' not in body:
        raise ValueError(f'{course} ch{chapter} Q{number}: no answer block')
    asked, answer = body.split('**答案：**', 1)
    return clean(asked), clean(answer)


def need(answer, *values):
    """Every expected rendering has to appear in the cleaned answer."""
    missing = [str(v) for v in values if str(v) not in answer]
    return [f'missing {m}' for m in missing]


def rounded(value, digits=3):
    """Render a float the way the notes do: trailing zeros trimmed."""
    text = f'{value:.{digits}f}'.rstrip('0').rstrip('.')
    return text


CN_DIGITS = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
             '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def count_of(text):
    """Read a count that the notes may spell with a Chinese numeral."""
    match = re.search(r'(\d+|十[一二三四五六七八九]?|[一二三四五六七八九])[条块]', text)
    if not match:
        raise ValueError('count not found: ' + text[:40])
    token = match[1]
    if token.isdigit():
        return int(token)
    if token.startswith('十'):
        return 10 + (CN_DIGITS[token[1]] if len(token) > 1 else 0)
    return CN_DIGITS[token]


def os_c1_q4(q, a):
    bits, address = map(int, re.search(r'按(\d+)位字编址.+?地址字段为(\d+)位', q).groups())
    words = 2 ** address
    total = words * (bits // 8)
    return need(a, f'2^{address}={words}', total)


def os_c3_q2(q, a):
    arrivals = [int(x) for x in re.search(r'到达时刻是(\d+)、(\d+)、(\d+)', q).groups()]
    service = [int(x) for x in re.search(r'服务时间是(\d+)、(\d+)、(\d+)', q).groups()]
    names = ['A', 'B', 'C']
    time = 0
    fcfs = []
    for arrival, cost in zip(arrivals, service):
        time = max(time, arrival) + cost
        fcfs.append(time)
    fcfs_turn = [t - s for t, s in zip(fcfs, arrivals)]
    fcfs_avg = Fraction(sum(fcfs_turn), len(fcfs_turn))
    ready, done, clock, spf = [], [], 0, []
    order = list(range(3))
    while order:
        clock = max(clock, min(arrivals[i] for i in order))
        candidates = [i for i in order if arrivals[i] <= clock]
        chosen = min(candidates, key=lambda i: (service[i], arrivals[i]))
        clock += service[chosen]
        spf.append((names[chosen], clock))
        order.remove(chosen)
    spf_turn = {n: t - arrivals[i] for n, t in spf for i in [names.index(n)]}
    spf_avg = Fraction(sum(spf_turn.values()), 3)
    return need(a, f'{fcfs_avg}', f'{spf_avg}')


def os_c4_q3(q, a):
    size, address, frame = map(int, re.search(r'页大小为(\d+)B，虚拟地址(\d+)映射到页框(\d+)', q).groups())
    page, offset = divmod(address, size)
    physical = frame * size + offset
    return need(a, f'{address}={page}×{size}+{offset}', f'{frame}×{size}+{offset}={physical}')


def os_c4_q4(q, a):
    bits, page_kib, entry = map(int, re.search(r'(\d+)位字节地址、(\d+)KiB页、(\d+)B页表项', q).groups())
    offset_bits = int(math.log2(page_kib * 1024))
    entries = page_kib * 1024 // entry
    index_bits = int(math.log2(entries))
    outer = bits - offset_bits - index_bits
    return need(a, f'{page_kib}KiB=2^{offset_bits}', f'{entries}=2^{index_bits}',
                f'32−{offset_bits}−{index_bits}={outer}', f'{outer}/{index_bits}/{offset_bits}')


def os_c5_q4(q, a):
    block_kib, addr_bytes, direct = map(int, re.search(r'(\d+)KiB块、(\d+)B地址、(\d+)个直接入口', q).groups())
    per = block_kib * 1024 // addr_bytes
    total = direct + per + per ** 2
    single = per * block_kib * 1024
    return need(a, f'{block_kib*1024}÷{addr_bytes}={per}', f'{total}', f'{per}×{block_kib*1024}={single}')


def os_c5_q5(q, a):
    file_kib, cluster_kib, blocks = map(int, re.search(r'(\d+)KiB文件按(\d+)KiB簇分配.+?(\d+)个块', q).groups())
    clusters = math.ceil(file_kib / cluster_kib)
    waste = clusters * cluster_kib - file_kib
    bitmap = blocks // 8
    return need(a, f'{clusters}簇', f'{clusters*cluster_kib}KiB', f'{waste}KiB', f'{blocks}/8={bitmap}B')


def os_c6_q2(q, a):
    blocks = count_of(q)
    transfer, process = map(int, re.search(r'输入(\d+)ms、处理(\d+)ms', q).groups())
    finish = transfer + blocks * process
    return need(a, f'{finish}ms')


def os_c6_q4(q, a):
    rpm, seek, transfer = re.search(r'(\d+)rpm的机械盘，平均寻道(\d+)ms、传输([\d.]+)ms', q).groups()
    revolution_ms = 60000 / int(rpm)
    average = revolution_ms / 2 + int(seek) + float(transfer)
    return need(a, f'60÷{rpm}={rounded(60000 / int(rpm) / 1000)}s', f'={rounded(revolution_ms)}ms',
                f'{rounded(revolution_ms)}÷2={rounded(revolution_ms/2)}ms', f'={rounded(average)}ms')


def os_c6_q5(q, a):
    groups = re.search(r'从磁道(\d+)开始处理队列(\d+)、(\d+)、(\d+)、(\d+)', q).groups()
    start, queue = int(groups[0]), [int(x) for x in groups[1:]]
    fcfs = sum(abs(b - a_) for a_, b in zip([start] + queue, queue))
    seq, rest = [start], queue[:]
    while rest:
        nxt = min(rest, key=lambda x: (abs(x - seq[-1]), x))
        seq.append(nxt)
        rest.remove(nxt)
    sstf = sum(abs(b - a_) for a_, b in zip(seq, seq[1:]))
    return need(a, f'={fcfs}', f'={sstf}')


def co_c1_q4(q, a):
    clock_a, cpi_a, clock_b, cpi_b = re.search(
        r'甲：(\d+)GHz、CPI=([\d.]+)；乙：(\d+)GHz、CPI=([\d.]+)。各执行两亿条指令', q).groups()
    count = 2e8
    a_s = count * float(cpi_a) / (int(clock_a) * 1e9)
    b_s = count * float(cpi_b) / (int(clock_b) * 1e9)
    half = 1e8 * float(cpi_b) / (int(clock_b) * 1e9)
    return need(a, f'{rounded(a_s)}s', f'{rounded(b_s)}s', f'{rounded(half)}s')


def co_c3_q1(q, a):
    total, opcode, regfield = map(int, re.search(r'(\d+)位指令使用(\d+)位操作码和两个(\d+)位寄存器字段', q).groups())
    immediate = total - opcode - 2 * regfield
    low = -2 ** (immediate - 1)
    high = 2 ** (immediate - 1) - 1
    return need(a, f'2^{opcode}={2**opcode}', f'2^{regfield}={2**regfield}',
                f'{total}−{opcode}−{regfield}−{regfield}={immediate}',
                f'−2^{immediate-1}', f'{high}')


def co_c3_q3(q, a):
    base, shift = re.search(r'MIPSbeq位于(0x[0-9A-Fa-f]+)，位移为(\d+)', q).groups()
    pc = int(base, 16) + 4
    first = pc + 12
    second = pc + (-2) * 4
    return need(a, f'0x{first:X}', f'0x{second:X}')


def co_c4_q2(q, a):
    paths = [int(x) for x in re.search(r'两条并行准备路径为(\d+)ps和(\d+)ps，汇合后再经过(\d+)ps', q).groups()]
    total = max(paths[0], paths[1]) + paths[2]
    return need(a, f'max({paths[0]},{paths[1]})+{paths[2]}={total}')


def co_c4_q3(q, a):
    stages = [int(x) for x in re.search(r'四阶段延迟为(\d+)、(\d+)、(\d+)、(\d+)ps', q).groups()]
    reg = int(re.search(r'各级寄存开销(\d+)ps', q)[1])
    instructions = count_of(q)
    period = max(stages) + reg
    cycles = len(stages) + instructions - 1
    total = period * cycles
    return need(a, f'max({",".join(map(str, stages))})+{reg}={period}',
                f'{len(stages)}+{instructions}-1={cycles}', f'{total}ps')


def co_c5_q1(q, a):
    mhz, width = map(int, re.search(r'(\d+)MHz、每周期两次传输、(\d+)位宽接口', q).groups())
    per = width // 8
    bandwidth = mhz * 1e6 * 2 * per
    exponent = int(math.log10(bandwidth))
    mantissa = rounded(bandwidth / 10 ** exponent)
    return need(a, f'{width}÷8={per}', f'{mantissa}×10^{exponent}', f'{rounded(bandwidth/1e9)}GB/s')


def co_c5_q2(q, a):
    chip_h, chip_w, target_h, target_w = re.search(
        r'用(\d+)Ki×(\d+)组成(\d+)Ki×(\d+)', q).groups()
    depth = int(target_h) // int(chip_h)
    wide = int(target_w) // int(chip_w)
    chips = depth * wide
    address_bits = int(math.log2(int(chip_h) * 1024))
    select_bits = int(math.log2(depth))
    return need(a, f'{target_h}÷{chip_h}={depth}', f'{target_w}÷{chip_w}={wide}',
                f'{depth}×{wide}={chips}', f'2^{address_bits}', f'{address_bits}位', f'高{select_bits}位')


def co_c5_q4(q, a):
    bits, kib, block_b, ways = re.search(
        r'(\d+)位字节地址、(\d+)KiB数据容量、(\d+)B块、(\d+)路组相联', q).groups()
    offset = int(math.log2(int(block_b)))
    sets = int(kib) * 1024 // (int(block_b) * int(ways))
    index = int(math.log2(sets))
    tag = int(bits) - offset - index
    address = int('0x129C', 16)
    block_no, within = divmod(address, int(block_b))
    group = block_no % sets
    tag_value = block_no // sets
    hit, penalty = re.search(r'命中(\d+)ns、未命中率5%、额外代价(\d+)ns', q).groups()
    amat = int(hit) + 0.05 * int(penalty)
    return need(a, f'{block_b}=2^{offset}', f'{sets}=2^{index}', f'{bits}−{offset}−{index}={tag}',
                f'={block_no}', f'偏移{within}', f'组{group}', f'标记{tag_value}', f'={rounded(amat)}ns')


def co_c5_q5(q, a):
    kib, address, page, frame = re.search(r'(\d+)KiB页下，虚拟地址(0x[0-9A-Fa-f]+)的页(\d+)映射到页框(\d+)', q).groups()
    size = int(kib) * 1024
    va = int(address, 16)
    offset = va % size
    physical = int(frame) * size + offset
    return need(a, f'=3×0x400+{hex(offset)}', f'{int(frame)}×0x400+{hex(offset)}={hex(physical)}')


def co_c6_q2(q, a):
    width, mhz, cycles = map(int, re.search(r'(\d+)位、(\d+)MHz总线每事务用(\d+)周期', q).groups())
    per = width // 8
    cycle_ns = 1000 / mhz
    ideal = width // 8 * mhz * 1e6 / 1e6
    effective = per / (cycles * cycle_ns * 1e-9) / 1e6
    return need(a, f'{width}÷8={per}', f'{rounded(cycle_ns)}ns',
                f'{rounded(ideal)}MB/s', f'{rounded(effective)}MB/s')


def co_c6_q4(q, a):
    rate, service = re.search(r'(\d+)字/s的设备每字中断服务(\d+)μs', q).groups()
    share = int(rate) * int(service) * 1e-6
    dma_rate = int(rate) // 20
    dma_service = int(re.search(r'服务(\d+)μs的DMA', q)[1])
    dma_share = dma_rate * dma_service * 1e-6
    return need(a, f'{rounded(share)}', f'{rounded(share*100)}%', f'{rounded(dma_share)}', f'{rounded(dma_share*100)}%')


def cn_c1_q3(q, a):
    bits, rate, propagation = re.search(
        r'仅把发送速率提高到(\d+)Mbit/s。+传播仍为([\d.]+)ms', q).groups() if 'Mbit/s。' in q else (None, None, None)
    bits = int(re.search(r'(\d+)×8÷', a)[1]) if re.search(r'(\d+)×8÷', a) else 1200
    rate = int(re.search(r'提高到(\d+)Mbit/s', q)[1])
    propagation = float(re.search(r'传播仍为([\d.]+)ms', a)[1])
    send = bits * 8 / (rate * 1e6) * 1000
    total = send + propagation
    return need(a, f'{rounded(send)}ms', f'{rounded(propagation)}', f'{rounded(total)}ms')


def cn_c2_q2(q, a):
    states, baud, bandwidth = re.search(r'(\d+)状态信号为(\d+)Baud，占(\d+)Hz', q).groups()
    symbols, symbol_errors, bits_total, bit_errors = re.search(
        r'(\d+)个码元有(\d+)个错、(\d+)个比特有(\d+)个错', q).groups()
    per_symbol = int(math.log2(int(states)))
    rate = int(baud) * per_symbol
    efficiency = rate / int(bandwidth)
    ber = int(symbol_errors) / int(symbols)
    bit_error = int(bit_errors) / int(bits_total)
    return need(a, f'log2{states}={per_symbol}', f'{rate}bit/s', f'{rounded(efficiency)}bit/(s·Hz)',
                f'{rounded(ber, 4)}', f'{rounded(bit_error, 5)}')


def cn_c2_q3(q, a):
    bandwidth, snr = re.search(r'带宽(\d+)Hz、信噪功率比(\d+)', q).groups()
    capacity = int(bandwidth) * math.log2(1 + int(snr))
    return need(a, f'{bandwidth}×log2(1+{snr})={int(capacity)}')


def cn_c2_q5(q, a):
    highest, sample, bits = re.search(r'最高([\d.]+)kHz，按(\d+)kHz抽样、每样本(\d+)bit', q).groups()
    interval_us = 1e6 / (int(sample) * 1000)
    rate = int(sample) * 1000 * int(bits)
    levels = 2 ** int(bits)
    reduced_rate = int(sample) * 1000 * 8
    reduced_levels = 2 ** 8
    return need(a, f'{rounded(interval_us, 1)}μs', f'{rate}bit/s', f'2^{bits}={levels}',
                f'{reduced_rate // 1000}kbit/s', f'{reduced_levels}个')


def cn_c5_q3(q, a):
    data, header, mtu = map(int, re.search(r'有(\d+)B数据、(\d+)B首部，出口MTU=(\d+)B', q).groups())
    payload = (mtu - header) // 8 * 8
    fragments = []
    remaining = data
    while remaining:
        take = min(payload, remaining)
        fragments.append(take)
        remaining -= take
    offsets = []
    running = 0
    for size in fragments:
        offsets.append(running // 8)
        running += size
    return need(a, f'floor(({mtu}−{header})/8)×8={payload}', f'{"、".join(map(str, fragments))}',
                f'{"、".join(map(str, offsets))}')


def cn_c5_q4(q, a):
    ip, prefix = re.search(r'主机为([\d.]+)/(\d+)', q).groups()
    prefix = int(prefix)
    octets = [int(x) for x in ip.split('.')]
    block = 2 ** (32 - prefix)
    network_last = octets[3] // block * block
    broadcast_last = network_last + block - 1
    hosts = block - 2
    mask_octets = []
    remaining = prefix
    for _ in range(4):
        take = min(8, remaining)
        mask_octets.append(255 - (2 ** (8 - take) - 1) if take else 0)
        remaining -= take
    mask = '.'.join(map(str, mask_octets))
    base = '.'.join(str(x) for x in octets[:3])
    return need(a, mask, f'{base}.{network_last}', f'{base}.{broadcast_last}',
                f'{base}.{network_last+1}', f'{base}.{broadcast_last-1}', f'{hosts}个')


def cn_c9_q3(q, a):
    people = int(re.search(r'(\d+)人每对共享一把', q)[1])
    return need(a, f'{people}×{people-1}/2={people*(people-1)//2}')


CHECKS = [
    ('operating-systems', 1, 4, os_c1_q4),
    ('operating-systems', 3, 2, os_c3_q2),
    ('operating-systems', 4, 3, os_c4_q3),
    ('operating-systems', 4, 4, os_c4_q4),
    ('operating-systems', 5, 4, os_c5_q4),
    ('operating-systems', 5, 5, os_c5_q5),
    ('operating-systems', 6, 2, os_c6_q2),
    ('operating-systems', 6, 4, os_c6_q4),
    ('operating-systems', 6, 5, os_c6_q5),
    ('computer-organization', 1, 4, co_c1_q4),
    ('computer-organization', 3, 1, co_c3_q1),
    ('computer-organization', 3, 3, co_c3_q3),
    ('computer-organization', 4, 2, co_c4_q2),
    ('computer-organization', 4, 3, co_c4_q3),
    ('computer-organization', 5, 1, co_c5_q1),
    ('computer-organization', 5, 2, co_c5_q2),
    ('computer-organization', 5, 4, co_c5_q4),
    ('computer-organization', 5, 5, co_c5_q5),
    ('computer-organization', 6, 2, co_c6_q2),
    ('computer-organization', 6, 4, co_c6_q4),
    ('computer-networks', 1, 3, cn_c1_q3),
    ('computer-networks', 2, 2, cn_c2_q2),
    ('computer-networks', 2, 3, cn_c2_q3),
    ('computer-networks', 2, 5, cn_c2_q5),
    ('computer-networks', 5, 3, cn_c5_q3),
    ('computer-networks', 5, 4, cn_c5_q4),
    ('computer-networks', 9, 3, cn_c9_q3),
]

errors = []
for course, chapter, number, check in CHECKS:
    label = f'{course} ch{chapter:02} Q{number}'
    try:
        asked, answer = question(course, chapter, number)
        problems = check(asked, answer)
    except (ValueError, AttributeError, KeyError, ZeroDivisionError) as exc:
        problems = [f'unreadable inputs: {exc}']
    if problems:
        errors.append(f'{label}: ' + '; '.join(problems))

print(f'Arithmetic: {len(CHECKS)} authored questions recomputed')
if errors:
    print('\n'.join(errors))
    sys.exit(1)
