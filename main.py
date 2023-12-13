import socket
import signal
import threading
import time
import jaconv
import requests
import websockets
import json
import asyncio
import re
import traceback

# Telnetcordの設定
config = json.loads(open("config.json", "r").read())
ver = "0.3"  # バージョン（変更禁止）
HOST = config['HOST']  # ホストIPアドレス
PORT = config['PORT']  # ポート番号（任意のポートを選択）
debug_flag = config['debug_flag']  # デバッグフラグ


# Ctrl+Cで終了する
def signal_handler(sig, frame):
    server_socket.close()
    print('Telnetcordを終了します。')
    exit(0)


def bytes_proc(command: bytes):
    command = command.replace(b"[A", b"")
    command = command.replace(b"[B", b"")
    command = command.replace(b"[C", b"")
    command = command.replace(b"[D", b"")
    command = command.replace(b"\x1b", b"")
    return command


def msg_proc(message: str):
    result = ""
    # @orange32サンクス
    for ch in message:
        if ch == "\x08":
            result = result[:len(result) - 1]
        else:
            result += ch
    return result


# クライアントとの通信を処理するスレッド
def handle_client(client_socket, client_address):
    # Telnetセッションを開始
    telnet_session = client_socket

    print(f"{client_address[0]} が接続しました。")
    telnet_session.send(b'\x1b[H\x1b[J')
    while True:
        # 文字コード選択
        telnet_session.send(f"\r\nPlease select a character code\r\n".encode('utf-8'))
        telnet_session.send("1. UTF-8\r\n"
                             "2. Shift_JIS\r\n"
                             "3. CP932\r\n".encode('utf-8'))
        telnet_session.send(f"[ ]\x1b[2D".encode('utf-8'))
        command = telnet_session.recv(1024)
        command = bytes_proc(command)
        text = command.decode('utf-8').replace("\r\n", "")
        text = msg_proc(text)
        charcode = ""
        if text == "1" or text == "１":
            charcode = "utf-8"
            break
        elif text == "2" or text == "２":
            charcode = "shift_jis"
            break
        elif text == "3" or text == "３":
            charcode = "cp932"
            break

        else:
            continue
    # クライアントと対話
    telnet_session.send(b'\x1b[H\x1b[J')
    telnet_session.send(f"\r\nTelnetcord Version {ver}\r\n".encode(charcode))
    while True:
        telnet_session.send("Tokenを入力してください: ".encode(charcode))
        command = telnet_session.recv(1024)
        command = bytes_proc(command)
        token = command.decode(charcode).replace("\r\n", "")
        token = msg_proc(token)
        if re.match(r"[\w-]{24}|[\w-]{26}\.[\w-]{6}\.[\w-]{38}", token):
            break
        else:
            continue
    r = requests.get("https://discord.com/api/v9/users/@me", headers={"authorization": token})
    result = r.json()
    if result['discriminator'] != "0":
        username = f"{result['username']}#{result['discriminator']}"
    else:
        username = result['username']
    # id = result["id"]

    # ハートビートの送信
    async def heartbeat(ws, interval):
        while True:
            # heartbeat interval sleep
            await asyncio.sleep((interval / 1000))
            try:
                await ws.send(json.dumps({"op": 1, "d": "null"}))
                continue
            except websockets.exceptions.ConnectionClosedOK:
                # 無視 websocketsのバグだと思ってる
                pass
            except websockets.exceptions.ConnectionClosedError:
                # 無視 websocketsのバグだと思ってる
                pass

    # 受信処理
    async def receive(ws):
        while True:
            try:
                data = json.loads(await ws.recv())
                if data['t'] == "MESSAGE_CREATE":
                    message = data['d']
                    try:
                        if message['channel_id'] == channelid:
                            if message['author']['discriminator'] != "0":
                                username = f"{message['author']['username']}#{message['author']['discriminator']}"
                            else:
                                username = message['author']['username']
                            message = f"\r{username}: {message['content']}\r\n"
                            telnet_session.send(message.encode(charcode))
                            telnet_session.send(f"> ".encode(charcode))
                    except NameError:
                        pass
                elif data['op'] == 7:
                    # 再接続
                    telnet_session.send("Discord Gatewayから切断されました。再接続します。".encode(charcode))
                    await runner()
                    await ws.send(json.dumps({"op": 1001, "d": "null"}))
                    return
                elif data['op'] == 9:
                    # Gatewayのエラー
                    telnet_session.send("Discord Gatewayにログインできませんでした。\r\n別のアカウントで試してください。".encode(charcode))
                    await ws.send(json.dumps({"op": 1001, "d": "null"}))
                    telnet_session.close()
                    return
                if debug_flag:
                    print(data)
            except websockets.exceptions.ConnectionClosedOK:
                # 無視 websocketsのバグだと思ってる
                pass
            except websockets.exceptions.ConnectionClosedError:
                # 無視 websocketsのバグだと思ってる
                pass

    # Gatewayの接続
    async def runner():
        identify = {
            "op": 2,
            "d": {
                "token": token,
                "intents": 3276799,
                "properties": {
                    "os" : "Windows",
                    "browser" : "Chrome",
                    "device" : "",
                    "system_locale": "ja",
                    "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "browser_version" : "120.0.0.0"
                },
                "presence": {
                    "activities": [{
                        "name": f"Telnetcord v{ver}",
                        "type": 0
                    }],
                    "status": "online",
                    "since": 0,
                    "afk": False
                },
            }
        }
        async with websockets.connect("wss://gateway.discord.gg/?v=10&encoding=json") as ws:
            # hello event receive
            hello_event = json.loads(await ws.recv())
            heartbeat_interval = hello_event['d']['heartbeat_interval']
            await ws.send(json.dumps(identify))
            telnet_session.send(f"\r{username}にログインしました。\r\n".encode(charcode))
            telnet_session.send(f"> ".encode(charcode))
            await asyncio.gather(
                heartbeat(ws, heartbeat_interval),
                receive(ws),
            )

    discord_handler = threading.Thread(target=asyncio.run, args=(runner(),))
    discord_handler.start()
    # デフォルトは有効
    jp_flag = 1
    telnet_session.send(f"> ".encode(charcode))
    while True:
        try:
            command = telnet_session.recv(1024)
            command = bytes_proc(command)
            command = command.decode(charcode)
            command = msg_proc(command)
            # helpコマンド
            if command == "help\r\n" or command == "HELP\r\n":
                telnet_session.send(
                    "bye: Telnetcordから切断します。\r\n"
                    "jp on/off: 日本語変換機能を有効/無効にします。\r\n"
                    "charcode: 文字コードを変更します。\r\n"
                    "list channel/guild: チャンネル、またはギルドの一覧を表示します。\r\n"
                    "select channel/guild [num]: チャンネル、またはギルドを選択します。\r\n"
                    "clear: 画面を消去します。\r\n"
                    "version: バージョン情報を表示します。\r\n"
                    "whatnew: 更新情報を表示します。\r\n".encode(charcode))
                telnet_session.send("> ".encode(charcode))
            # byeコマンド
            elif command == "bye\r\n" or command == "BYE\r\n":
                telnet_session.close()
                print(f"{client_address[0]} が切断しました。")
                break
            # jpコマンド
            elif command.startswith("jp") or command.startswith("JP"):
                args = command.replace("\r\n", "").split(" ")
                if len(args) == 2:
                    arg = args[1]
                    if arg:
                        jp_flag = 0
                        if arg == "on" or arg == "ON":
                            jp_flag = 1
                            telnet_session.send("\r日本語変換が有効になりました。\r\n".encode(charcode))
                        elif arg == "off" or arg == "OFF":
                            jp_flag = 0
                            telnet_session.send("\r日本語変換が無効になりました。\r\n".encode(charcode))
                        else:
                            telnet_session.send(f"\r引数が間違っています。\r\n".encode(charcode))
                else:
                    telnet_session.send(f"\r引数が間違っています。\r\n".encode(charcode))
                telnet_session.send("> ".encode(charcode))
            # charcodeコマンド
            elif command == "charcode\r\n" or command == "CHARCODE\r\n":
                while True:
                    telnet_session.send(f"\r\nPlease select a character code\r\n".encode('utf-8'))
                    telnet_session.send("1. UTF-8\r\n"
                                         "2. Shift_JIS\r\n"
                                         "3. CP932\r\n".encode('utf-8'))
                    telnet_session.send(f"[ ]\x1b[2D".encode('utf-8'))
                    command = telnet_session.recv(1024)
                    text = command.decode('utf-8').replace("\r\n", "")
                    charcode = ""
                    if text == "1" or text == "１":
                        charcode = "utf-8"
                        telnet_session.send("\r文字コードはUTF-8に設定されました。\r\n".encode(charcode))
                        break
                    elif text == "2" or text == "２":
                        charcode = "shift_jis"
                        telnet_session.send("\r文字コードはShift_JISに設定されました。\r\n".encode(charcode))
                        break
                    elif text == "3" or text == "３":
                        charcode = "cp932"
                        telnet_session.send("\r\n文字コードはCP932に設定されました。\r\n".encode(charcode))
                        break
                    else:
                        continue
                telnet_session.send("> ".encode(charcode))
            # clearコマンド
            elif command == "clear\r\n" or command == "CLEAR\r\n":
                telnet_session.send(b'\x1b[H\x1b[J')
                telnet_session.send("> ".encode(charcode))
            # versionコマンド
            elif command == "version\r\n" or command == "VERSION\r\n":
                telnet_session.send(f"Telnetcord Version {ver}\r\n".encode(charcode))
                telnet_session.send("> ".encode(charcode))
            # whatnewコマンド
            elif command == "whatnew\r\n" or command == "WHATNEW\r\n":
                telnet_session.send(f"Telnetcord Version {ver}\r\n"
                                     "・トークン判定の正規表現を改良\r\n"
                                     "・CP932への対応\r\n"
                                     "・履歴機能の追加\r\n"
                                     "・telnetlibを使わないようにした\r\n"
                                     "・identifyをWindowsのChromeに変更\r\n"
                                     "・ログインメッセージのユーザー名を統一\r\n".encode(charcode))
                telnet_session.send("> ".encode(charcode))
            # selectコマンド
            elif command.startswith("select") or command.startswith("SELECT"):
                args = command.replace("\r\n", "").split(" ")
                if len(args) == 3:
                    mode = args[1]
                    arg = args[2]
                    if mode:
                        if mode == "guild" or mode == "GUILD":
                            r = requests.get("https://discord.com/api/v9/users/@me/guilds",
                                             headers={"Content-Type": "application/json", "authorization": token})
                            result = r.json()
                            try:
                                guildid = result[int(arg)]['id']
                                telnet_session.send(f"\r{result[int(arg)]['name']}を選択しました。\r\n".encode(charcode))
                            except IndexError:
                                telnet_session.send(f"\r引数が間違っています。\r\n".encode(charcode))
                                pass
                        elif mode == "channel" or mode == "CHANNEL":
                            try:
                                r = requests.get(f"https://discord.com/api/v9/guilds/{guildid}/channels", headers={"Content-Type": "application/json", "authorization": token})
                                result = r.json()
                                TextChannelList = []
                                for TextChannel in result:
                                    if TextChannel['type'] == 0:
                                        TextChannelList.append(TextChannel)
                                try:
                                    channelid = TextChannelList[int(arg)]['id']
                                    telnet_session.send(f"\r{TextChannelList[int(arg)]['name']}を選択しました。\r\n".encode(charcode))
                                except IndexError:
                                    telnet_session.send(f"\r引数が間違っています。\r\n".encode(charcode))
                                    pass
                                history = ""
                                r = requests.get(f"https://discord.com/api/v9/channels/{channelid}/messages?limit=50",
                                                 headers={"Content-Type": "application/json", "authorization": token})
                                msgs = r.json()
                                # 逆にして古い順
                                msgs.reverse()
                                for msg in msgs:
                                    if msg['author']['discriminator'] != "0":
                                        username = f"{msg['author']['username']}#{msg['author']['discriminator']}"
                                    else:
                                        username = msg['author']['username']
                                    history += f"{username}: {msg['content']}\r\n"
                                telnet_session.send(history.encode(charcode))
                            except NameError:
                                telnet_session.send(f"\rサーバーが選択されていません。selectコマンドで選択してください。\r\n".encode(charcode))
                                pass
                        else:
                            telnet_session.send(f"\r引数が間違っています。\r\n".encode(charcode))
                else:
                    telnet_session.send(f"\r引数が間違っています。\r\n".encode(charcode))
                telnet_session.send("> ".encode(charcode))
            # listコマンド
            elif command.startswith("list") or command.startswith("LIST"):
                args = command.replace("\r\n", "").split(" ")
                if len(args) == 2:
                    mode = args[1]
                    if mode:
                        if mode == "guild" or mode == "GUILD":
                            r = requests.get("https://discord.com/api/v9/users/@me/guilds",
                                             headers={"Content-Type": "application/json", "authorization": token})
                            result = r.json()
                            guildList = ""
                            for i, guildDict in enumerate(result):
                                guildList += f"[{i}] {guildDict['name']}({guildDict['id']})\r\n"
                            telnet_session.send(guildList.encode(charcode))
                        elif mode == "channel" or mode == "CHANNEL":
                            try:
                                r = requests.get(f"https://discord.com/api/v9/guilds/{guildid}/channels",
                                                 headers={"Content-Type": "application/json", "authorization": token})
                                result = r.json()
                                TextChannelList = []
                                for TextChannel in result:
                                    if TextChannel['type'] == 0:
                                        TextChannelList.append(TextChannel)
                                channelList = ""
                                for i, channelDict in enumerate(TextChannelList):
                                    channelList += f"[{i}] {channelDict['name']}({channelDict['id']})\r\n"
                                telnet_session.send(channelList.encode(charcode))
                            except NameError:
                                telnet_session.send(f"\rサーバーが選択されていません。selectコマンドで選択してください。\r\n".encode(charcode))
                                pass
                        else:
                            telnet_session.send(f"\r引数が間違っています。\r\n".encode(charcode))
                else:
                    telnet_session.send(f"\r引数が間違っています。\r\n".encode(charcode))
                telnet_session.send("> ".encode(charcode))
            # 空白対策
            elif command == " " or command == "\r\n":
                telnet_session.send("> ".encode(charcode))
            # メッセージの処理
            else:
                if jp_flag:
                    if re.search(r'[ぁ-ん]+|[ァ-ヴー]+|[一-龠]+', command):
                        pass
                    else:
                        i = 0
                        text = ""
                        temp_msg = command
                        # ヘボン式ローマ字がなんちゃら
                        temp_msg = temp_msg.replace("si", "shi")
                        temp_msg = temp_msg.replace("wi", "whi")
                        temp_msg = temp_msg.replace("we", "whe")
                        msg = jaconv.alphabet2kana(temp_msg)
                        dicRes = requests.get(
                            f"http://www.google.com/transliterate?langpair=ja-Hira|ja&text={msg}").json()
                        while i < len(dicRes):
                            text += dicRes[i][1][0]
                            i += 1
                        command = text
                        pass
                else:
                    pass
                try:
                    r = requests.post(f"https://discord.com/api/v9/channels/{channelid}/messages",
                                      json={"content": command},
                                      headers={"Content-Type": "application/json", "authorization": token})
                    if r.status_code == 200:
                        pass
                    else:
                        telnet_session.send("\rメッセージの送信に失敗しました。\r\n".encode(charcode))
                        telnet_session.send("> ".encode(charcode))
                except NameError:
                    telnet_session.send(f"\rチャンネルが選択されていません。selectコマンドで選択してください。\r\n".encode(charcode))
                    telnet_session.send("> ".encode(charcode))
        except Exception:
            if debug_flag:
                print(traceback.format_exc())
            pass
            #telnet_session.close()
            #print(f"{client_address[0]} が切断しました。")
            #break

print("\x1b[H\x1b[J")
print(f"Telnetcord Version {ver}")
signal.signal(signal.SIGINT, signal_handler)
# ソケットを作成してバインド
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
while True:
    try:
        server_socket.bind((HOST, PORT))
        break
    except OSError:
        print(f"システムが{PORT}番ポートを使用中です、10秒後に再試行します。")
        time.sleep(10)
        continue
server_socket.listen(10)  # 接続を待ち受ける最大クライアント数
print(f"{PORT}番ポートでTelnetcordが起動しました\n")

while True:
    client_socket, client_address = server_socket.accept()
    client_handler = threading.Thread(target=handle_client, args=(client_socket, client_address))
    client_handler.start()
