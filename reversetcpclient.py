#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TCP 反转文本客户端 (Reverse TCP Client)
功能：读取本地文本文件，分块发送给服务器反转，最终输出完整反转文件

运行方式：
    python reversetcpclient.py <serverIP> <serverPort> <Lmin> <Lmax> <seed> <input_file> [output_file]

    参数说明：
        serverIP:   服务器IP地址（如 127.0.0.1 或 192.168.1.100）
        serverPort: 服务器端口号（如 12345）
        Lmin:       每块最小字节数（如 50）
        Lmax:       每块最大字节数（如 100）
        seed:       随机数种子（确保可复现，如 42）
        input_file: 要反转的文本文件路径
        output_file: 输出文件路径（可选，默认 input_file + ".reversed"）

    例如：
        python reversetcpclient.py 127.0.0.1 12345 50 100 42 test.txt
"""

import socket      # 网络编程库
import struct      # 二进制数据打包/解包
import random      # 随机数生成，用于确定每块长度
import time        # 时间戳记录
import sys         # 命令行参数
import os          # 文件操作

# ========== 报文类型常量==========
TYPE_INIT = 1      # Initialization
TYPE_AGREE = 2     # agree
TYPE_REQUEST = 3   # reverseRequest
TYPE_ANSWER = 4    # reverseAnswer

LOG_FILE = "run_log.txt"


def log_event(direction, msg_type_name, details=""):
    """
    记录通信事件到日志文件

    参数：
        direction: "C->S" 或 "S->C"
        msg_type_name: 报文类型名称
        details: 额外信息
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    ms = int((time.time() % 1) * 1000)
    timestamp += f".{ms:03d}"

    line = f"[{timestamp}] [{direction}] {msg_type_name} {details}\n"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)

    print(line.strip())


def recv_exact(sock, n):
    """
    【关键函数】确保精确接收 n 个字节
    recv(n) 不一定返回 n 字节。
    这个函数循环读取，直到凑够 n 字节。
    参数：
        sock: 网络连接
        n: 需要接收的字节数
    返回：
        bytes 数据，连接断开返回 None
    """
    data = b""
    while len(data) < n:
        remaining = n - len(data)
        chunk = sock.recv(remaining)
        if not chunk:
            return None
        data += chunk
    return data


def split_file(file_path, Lmin, Lmax, seed):
    """
    【核心算法】将文件按随机长度分块
    算法步骤：
        1. 读取整个文件内容
        2. 用 random 生成 [Lmin, Lmax] 范围内的随机数作为每块长度
        3. 最后一块可能小于 Lmin->文件末尾剩余部分
        4. 返回：块数 N，以及每块的起始位置和长度列表
    seed的意义：
        随机数种子让"随机"变得可复现。
        同样的 seed 总会生成同样的随机数序列，方便调试和验收。
    参数：
        file_path: 文件路径
        Lmin: 每块最小字节数
        Lmax: 每块最大字节数
        seed: 随机数种子

    返回：
        (N, chunks) 其中 chunks 是 [(start, length), ...] 的列表
    """
    # 读取文件全部内容（因为是ASCII文本，二进制读取更安全）
    with open(file_path, "rb") as f:
        content = f.read()

    total_len = len(content)
    print(f"[信息] 文件总大小: {total_len} 字节")

    # 设置随机数种子，确保结果可复现
    random.seed(seed)

    chunks = []      # 存储每块的信息：(起始位置, 长度)
    pos = 0          # 当前处理到的文件位置

    while pos < total_len:
        # 计算剩余未处理的字节数
        remaining = total_len - pos

        if remaining <= Lmax:
            # 剩余部分不够一个完整块，全部作为最后一块
            # 注意：最后一块可以小于 Lmin，这是题目允许的
            chunk_len = remaining
        else:
            # 正常情况：在 [Lmin, Lmax] 范围内随机选择长度
            # random.randint(a, b) 生成 [a, b] 范围内的整数（包含两端）
            chunk_len = random.randint(Lmin, Lmax)

        chunks.append((pos, chunk_len))
        pos += chunk_len

    N = len(chunks)
    print(f"[信息] 分块完成: 共 {N} 块")
    for i, (start, length) in enumerate(chunks):
        print(f"       第 {i+1} 块: 起始位置={start}, 长度={length}")

    return N, chunks, content


def main():
    """
    客户端主函数：连接服务器，发送文件，接收反转结果
    """
    # ========== 解析命令行参数 ==========
    if len(sys.argv) < 7:
        print("用法: python reversetcpclient.py <serverIP> <serverPort> <Lmin> <Lmax> <seed> <input_file> [output_file]")
        print("例如: python reversetcpclient.py 127.0.0.1 12345 50 100 42 test.txt")
        sys.exit(1)

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    Lmin = int(sys.argv[3])
    Lmax = int(sys.argv[4])
    seed = int(sys.argv[5])
    input_file = sys.argv[6]

    # 输出文件名：如果没指定，就用 "原文件名.reversed"
    if len(sys.argv) >= 8:
        output_file = sys.argv[7]
    else:
        output_file = input_file + ".reversed"

    print(f"=" * 50)
    print(f"[配置] 服务器: {server_ip}:{server_port}")
    print(f"[配置] 分块范围: [{Lmin}, {Lmax}], 随机种子: {seed}")
    print(f"[配置] 输入文件: {input_file}")
    print(f"[配置] 输出文件: {output_file}")
    print(f"=" * 50)

    # ========== 第1步：分块 ==========
    N, chunks, file_content = split_file(input_file, Lmin, Lmax, seed)

    # ========== 第2步：连接服务器 ==========
    # 创建 TCP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # connect() 建立到服务器的连接
    # 如果服务器没启动，这里会报错（ConnectionRefusedError）
    sock.connect((server_ip, server_port))
    print(f"[连接] 已连接到服务器 {server_ip}:{server_port}")

    try:
        # ========== 第3步：发送 Initialization 报文 ==========
        # 格式：| Type(2字节) | N(4字节) |
        init_packet = struct.pack("!H", TYPE_INIT)    # 类型 = 1
        init_packet += struct.pack("!I", N)            # 块数 N

        sock.sendall(init_packet)
        log_event("C->S", "Initialization", f"N={N}")

        # ========== 第4步：接收 agree 报文 ==========
        # agree 只有 2 字节（Type字段）
        agree_data = recv_exact(sock, 2)
        if agree_data is None:
            print("[错误] 服务器断开连接")
            return

        agree_type = struct.unpack("!H", agree_data)[0]

        if agree_type != TYPE_AGREE:
            print(f"[错误] 收到非agree报文，类型={agree_type}")
            return

        log_event("S->C", "agree", f"服务器同意处理 {N} 块")
        print(f"[握手] 服务器已同意，开始传输 {N} 块数据...")

        # ========== 第5步：逐块发送 reverseRequest，接收 reverseAnswer ==========
        all_reversed = []  # 收集所有反转后的块，最后拼接成完整文件

        for i in range(N):
            start, length = chunks[i]

            # 从文件内容中切出当前块的数据
            chunk_data = file_content[start:start + length]

            # 组装 reverseRequest 报文
            # 格式：| Type(2字节) | Length(4字节) | Data(Length字节) |
            req_packet = struct.pack("!H", TYPE_REQUEST)       # 类型 = 3
            req_packet += struct.pack("!I", length)             # 数据长度
            req_packet += chunk_data                            # 数据本身

            sock.sendall(req_packet)

            # 将二进制数据解码为字符串，用于日志显示
            text = chunk_data.decode("ascii")
            log_event("C->S", "reverseRequest",
                      f"第{i+1}/{N}块, 长度={length}, 内容=\"{text[:30]}{'...' if len(text)>30 else ''}\"")

            # 接收 reverseAnswer 报文
            # 先读头部 6 字节（Type + Length）
            ans_header = recv_exact(sock, 6)
            if ans_header is None:
                print(f"[错误] 接收第 {i+1} 块回复时连接断开")
                return

            ans_type = struct.unpack("!H", ans_header[0:2])[0]
            ans_len = struct.unpack("!I", ans_header[2:6])[0]

            # 再读反转后的数据
            reversed_data = recv_exact(sock, ans_len)
            if reversed_data is None:
                print(f"[错误] 接收第 {i+1} 块数据时连接断开")
                return

            reversed_text = reversed_data.decode("ascii")

            log_event("S->C", "reverseAnswer",
                      f"第{i+1}/{N}块, 长度={ans_len}")

            # 题目要求：在命令行打印 "第 x 块：反转的文本"
            print(f"第 {i+1} 块：{reversed_text}")

            # 收集反转后的文本
            all_reversed.append(reversed_text)

        '''
        ========== 第6步：拼接并输出最终文件 ==========
        原始文件 = chunk1 + chunk2 + ... + chunkN
        全部反转 = reverse(chunkN) + reverse(chunkN-1) + ... + reverse(chunk1)

        服务器返回的是每块"单独反转"的结果。
        要得到"原始文件的全部反转"，需要把各块的反转结果按"倒序"拼接。
        '''
        final_content = "".join(reversed(all_reversed))

        with open(output_file, "w", encoding="ascii") as f:
            f.write(final_content)

        print(f"\n[完成] 反转结果已保存到: {output_file}")
        print(f"[完成] 文件大小: {len(final_content)} 字节")

        # 验证：直接反转原始文件，看结果是否一致
        with open(input_file, "rb") as f:
            original = f.read().decode("ascii")
        expected = original[::-1]

        if final_content == expected:
            print("成功")
        else:
            print("失败")

    except Exception as e:
        print(f"通信异常: {e}")
    finally:
        sock.close()
        print("连接已关闭")


if __name__ == "__main__":
    main()