# telnetcord
TelnetでDiscordクライアントを実装しようか

## アップデート履歴
### v0.1
- 全てはここから始まった
- 基本的な機能を実装

### v0.2
- トークン判定を正規表現で対応
- 微量の修正
- Gatewayの実装をTelnetチャットv0.4.8に追従

### v0.3
- トークン判定の正規表現を改良
- CP932への対応
- 履歴機能の追加
- telnetlibを使わないようにした
- identifyをWindowsのChromeに変更
- ログインメッセージのユーザー名を統一

## config.jsonの書き方
```json
{
  "HOST": "0.0.0.0", // TelnetcordをホストするIP、0.0.0.0から変えないでください
  "PORT": 23, // Telnetcordをホストするポート番号
  "debug_flag": false // エラーログやGatewayのログを出力するかどうか、falseがデフォルトです
}
```

## 謎バグ
なぜかGatewayにログインできないことがある 原因不明