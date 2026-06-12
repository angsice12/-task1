task1主题
------------
  TCP Socket programming

一、运行环境
------------
  - Python 3.6 或更高版本

二、文件说明
------------
  reversetcpserver.py    服务器端程序（运行在 guest OS）
  reversetcpclient.py    客户端程序（运行在 host OS）
  run_log.txt            自动生成的通信日志（程序运行时自动创建）
  readme.txt             本说明文件

三、快速开始
------------

  1. 启动服务器（先开服务器，再开客户端）

     python reversetcpserver.py 12345

     参数：端口号（任意 1024~65535 之间的数字）
     示例输出：
       [启动] 反转文本服务器已启动
       [监听] 正在监听端口 12345，等待客户端连接...

  2. 准备测试文件

     创建一个纯英文 ASCII 文本文件，例如 test.txt：

     echo "Hello World! This is a test file for TCP socket programming." > test.txt

     注意：文件必须只包含英文可打印 ASCII 字符！

  3. 启动客户端

     python reversetcpclient.py 127.0.0.1 12345 10 20 42 test.txt

     参数说明：
       127.0.0.1    服务器IP地址（本机测试用127.0.0.1）
       12345        服务器端口号（必须与服务器一致）
       10           Lmin（每块最小字节数）
       20           Lmax（每块最大字节数）
       42           随机数种子（确保分块结果可复现）
       test.txt     输入文件路径

     可选第8个参数指定输出文件名：
       python reversetcpclient.py ... test.txt output.txt
     不指定则默认输出到 test.txt.reversed

四、分块算法说明
----------------

  分块是验收的重点，算法如下：

  1. 读取文件全部内容，得到总字节数 total_len
  2. 设置随机数种子：random.seed(seed)
  3. 从文件开头开始，循环生成每块长度：

     while 还有未处理的字节:
         remaining = 剩余字节数
         if remaining <= Lmax:
             最后一块 = remaining（可以小于Lmin，这是正常的）
         else:
             块长度 = random.randint(Lmin, Lmax)
         记录这块的起始位置和长度
         指针前进

  4. 计算块数 N = 块的总数

  举例验证：
    文件大小 520 字节，Lmin=50，Lmax=100，seed=42
    random 依次生成：90, 57, 51, 97, 67, 65, 93（最后一块=剩余93 ≤ Lmax）

    第1块: 长度 90,  范围 [0, 89]      剩余 520-90=430
    第2块: 长度 57,  范围 [90, 146]    剩余 430-57=373
    第3块: 长度 51,  范围 [147, 197]   剩余 373-51=322
    第4块: 长度 97,  范围 [198, 294]   剩余 322-97=225
    第5块: 长度 67,  范围 [295, 361]   剩余 225-67=158
    第6块: 长度 65,  范围 [362, 426]   剩余 158-65=93
    第7块: 长度 93,  剩余只有93 <= Lmax(100)，所以最后一块=93
            范围 [427, 519]

    N = 7
    第3块起始字节 = 90+57 = 147

  代码中对应函数：reversetcpclient.py 中的 split_file() 函数

五、报文格式
------------

  本程序使用自定义应用层协议，4种报文：

  1. Initialization (C->S, Type=1)
     | Type(2字节) | N(4字节) |
     说明：客户端告诉服务器"我要发N个数据块"

  2. agree (S->C, Type=2)
     | Type(2字节) |
     说明：服务器回复"好的，我准备好了"

  3. reverseRequest (C->S, Type=3)
     | Type(2字节) | Length(4字节) | Data(Length字节) |
     说明：客户端发送一段文本，请求反转

  4. reverseAnswer (S->C, Type=4)
     | Type(2字节) | Length(4字节) | reverseData(Length字节) |
     说明：服务器返回反转后的文本

  所有数字字段使用网络字节序（大端序），Python 中用 struct.pack("!H") 和 struct.pack("!I") 处理。

六、日志文件 run_log.txt
--------------------------

  每次收发报文都会记录，格式：
    [YYYY-MM-DD HH:MM:SS.mmm] [方向] 报文类型 详细信息

  示例：
    [2026-06-04 12:30:15.123] [C->S] Initialization N=7
    [2026-06-04 12:30:15.145] [S->C] agree N=7 发往('127.0.0.1', 54321)
    [2026-06-04 12:30:15.200] [C->S] reverseRequest 第1/7块, 长度=73
    [2026-06-04 12:30:15.250] [S->C] reverseAnswer 第1/7块, 长度=73

  日志中的时间戳应与 Wireshark 抓包时间对应，便于验收核对。

七、多客户端支持
----------------

  服务器使用 threading 模块，为每个客户端连接创建独立线程。
  因此可以同时运行多个客户端，服务器会并行处理。

  测试方法：
    终端1: python reversetcpserver.py 12345
    终端2: python reversetcpclient.py 127.0.0.1 12345 10 20 42 file1.txt
    终端3: python reversetcpclient.py 127.0.0.1 12345 15 30 99 file2.txt

