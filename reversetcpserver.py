#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TCP 反转文本服务器 (Reverse TCP Server)
功能：接收客户端发来的文本块，将其反转后返回，支持多客户端并发处理

运行方式：
    python reversetcpserver.py <端口号>
    例如：python reversetcpserver.py 12345
"""

import socket      # 网络编程库，提供TCP/UDP通信功能
import struct      # 二进制数据打包/解包库（处理报文中的数字字段）
import threading   # 多线程库，让服务器能同时服务多个客户端
import time        # 时间库，用于记录日志时间戳
import sys         # 系统参数，获取命令行输入的端口号

# ========== 报文类型常量（协议规定）==========
# 这些数字就像"快递单上的货物类型标签"，让收发双方知道包裹里是什么
TYPE_INIT = 1      # Initialization：客户端告诉服务器"我要发N个块"
TYPE_AGREE = 2     # agree：服务器回复"好的，我准备好了"
TYPE_REQUEST = 3   # reverseRequest：客户端发送"请帮我反转这段文本"
TYPE_ANSWER = 4    # reverseAnswer：服务器回复"这是反转后的文本"

# 日志文件名（固定）
LOG_FILE = "run_log.txt"


def log_event(direction, msg_type_name, details=""):
    """
    记录通信事件到日志文件

    参数：
        direction: 方向，如 "C->S" 表示 Client发往Server，"S->C" 表示 Server发往Client
        msg_type_name: 报文类型名称，如 "Initialization"
        details: 额外信息，如数据长度等
    """
    # 获取当前时间，格式：2026-06-04 12:30:45.123
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    # 毫秒部分
    ms = int((time.time() % 1) * 1000)
    timestamp += f".{ms:03d}"

    line = f"[{timestamp}] [{direction}] {msg_type_name} {details}\n"

    # "a" 表示 append（追加），不会覆盖之前的日志
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)

    # 同时在控制台打印，方便调试观察
    print(line.strip())


def recv_exact(sock, n):
    """
    【关键函数】确保从网络中精确接收 n 个字节

    为什么需要这个函数？
    TCP 是"流式"协议，数据像水流一样连续传输。
    调用 recv(10) 不一定能收到10字节，可能只收到3字节。
    这个函数会不断读取，直到凑够 n 个字节为止。

    参数：
        sock: 网络连接对象（socket）
        n: 需要接收的字节数

    返回：
        bytes 类型的数据，如果连接断开则返回 None
    """
    data = b""  # 空字节串，用来"攒"数据
    while len(data) < n:
        # 还需要读多少字节
        remaining = n - len(data)
        # 从网络读取，最多读 remaining 字节
        chunk = sock.recv(remaining)
        if not chunk:
            # chunk 为空表示对方已断开连接
            return None
        data += chunk
    return data


def handle_client(client_sock, client_addr):
    """
    【核心函数】处理单个客户端的完整通信流程（在独立线程中运行）

    每个客户端连接都会启动一个新线程执行此函数，
    这样多个客户端可以同时被服务，互不干扰。

    参数：
        client_sock: 与这个客户端建立的网络连接
        client_addr: 客户端的IP地址和端口号
    """
    print(f"\n[新连接] 客户端 {client_addr} 已接入")

    try:
        # ========== 第1步：接收 Initialization 报文 ==========
        # Initialization 报文格式：| Type(2字节) | N(4字节) |
        # 共 6 个字节
        header = recv_exact(client_sock, 6)
        if header is None:
            print(f"[断开] 客户端 {client_addr} 在初始化前断开")
            return

        # struct.unpack("!H", ...) 将2字节二进制转成数字
        # "!" 表示网络字节序（大端序），"H" 表示无符号短整型（2字节）
        msg_type = struct.unpack("!H", header[0:2])[0]
        # "!I" 表示无符号整型（4字节）
        N = struct.unpack("!I", header[2:6])[0]

        # 记录接收日志
        log_event("C->S", "Initialization", f"N={N} 来自{client_addr}")

        # ========== 第2步：发送 agree 报文 ==========
        # agree 报文格式：| Type(2字节) |
        # 只有类型字段，告诉客户端"我同意，开始吧"
        agree_packet = struct.pack("!H", TYPE_AGREE)
        client_sock.sendall(agree_packet)

        # 记录发送日志
        log_event("S->C", "agree", f"N={N} 发往{client_addr}")

        print(f"[处理中] 客户端 {client_addr} 将发送 {N} 个数据块")

        # ========== 第3步：循环处理 N 个 reverseRequest ==========
        for i in range(N):
            # 接收 reverseRequest 报文头部
            # 格式：| Type(2字节) | Length(4字节) | Data(Length字节) |
            # 先读头部 6 字节
            req_header = recv_exact(client_sock, 6)
            if req_header is None:
                print(f"[错误] 客户端 {client_addr} 在第 {i+1}/{N} 块时断开")
                return

            req_type = struct.unpack("!H", req_header[0:2])[0]
            data_len = struct.unpack("!I", req_header[2:6])[0]

            # 再读 Data 部分（真正的文本内容）
            data = recv_exact(client_sock, data_len)
            if data is None:
                print(f"[错误] 客户端 {client_addr} 数据接收中断")
                return

            # 将二进制数据解码为字符串（ASCII编码）
            text = data.decode("ascii")

            # 记录接收日志
            log_event("C->S", "reverseRequest", 
                      f"第{i+1}/{N}块, 长度={data_len}, 内容=\"{text[:20]}{'...' if len(text)>20 else ''}\"")

            # ========== 第4步：反转文本并发送 reverseAnswer ==========
            # Python 字符串反转非常简单：text[::-1]
            # [::-1] 表示"从头到尾，步长为-1"，即倒序
            reversed_text = text[::-1]
            reversed_data = reversed_text.encode("ascii")
            reversed_len = len(reversed_data)

            # 组装 reverseAnswer 报文
            # 格式：| Type(2字节) | Length(4字节) | reverseData(Length字节) |
            answer_packet = struct.pack("!H", TYPE_ANSWER)       # 类型
            answer_packet += struct.pack("!I", reversed_len)     # 长度
            answer_packet += reversed_data                       # 反转后的数据

            client_sock.sendall(answer_packet)

            # 记录发送日志
            log_event("S->C", "reverseAnswer",
                      f"第{i+1}/{N}块, 长度={reversed_len}, 内容=\"{reversed_text[:20]}{'...' if len(reversed_text)>20 else ''}\"")

        print(f"[完成] 客户端 {client_addr} 全部 {N} 块处理完毕")

    except Exception as e:
        print(f"[异常] 处理客户端 {client_addr} 时出错: {e}")
    finally:
        # 无论成功还是失败，最后都要关闭连接
        client_sock.close()
        print(f"[关闭] 与客户端 {client_addr} 的连接已关闭")


def main():
    """
    服务器主函数：创建监听端口，等待客户端连接
    """
    # 检查命令行参数
    if len(sys.argv) != 2:
        print("用法: python reversetcpserver.py <端口号>")
        print("例如: python reversetcpserver.py 12345")
        sys.exit(1)

    port = int(sys.argv[1])

    # 创建 TCP socket
    # socket.AF_INET 表示使用 IPv4 地址
    # socket.SOCK_STREAM 表示使用 TCP 协议（面向连接的可靠传输）
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # 设置端口复用，服务器重启后可以立即再次绑定同一端口
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # 绑定到本机所有IP地址（"0.0.0.0"）和指定端口
    server_sock.bind(("0.0.0.0", port))

    # 开始监听，backlog=5 表示最多允许5个客户端排队等待连接
    server_sock.listen(5)

    print(f"=" * 50)
    print(f"[启动] 反转文本服务器已启动")
    print(f"[监听] 正在监听端口 {port}，等待客户端连接...")
    print(f"[日志] 通信日志将写入: {LOG_FILE}")
    print(f"=" * 50)

    try:
        while True:
            # accept() 是阻塞调用：没有客户端连接时，程序会暂停在这里等待
            # 当有客户端连接时，返回：(新连接对象, 客户端地址)
            client_sock, client_addr = server_sock.accept()

            # 为每个客户端创建独立线程
            # target=handle_client 表示线程要执行的函数
            # args=(...) 传给函数的参数
            # daemon=True 表示主程序退出时这些线程也会自动退出
            t = threading.Thread(
                target=handle_client,
                args=(client_sock, client_addr),
                daemon=True
            )
            t.start()

            # 显示当前活跃的线程数（即正在服务的客户端数）
            active = threading.active_count() - 1  # 减去主线程
            print(f"[线程] 当前活跃客户端数: {active}")

    except KeyboardInterrupt:
        # Ctrl+C 按下时优雅退出
        print("\n[关闭] 收到中断信号，服务器正在关闭...")
    finally:
        server_sock.close()
        print("[关闭] 服务器已停止")


if __name__ == "__main__":
    main()