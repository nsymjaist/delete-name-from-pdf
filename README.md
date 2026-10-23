# delete name from pdf
PDFファイルから指定した文字列を消すツール


# 使い方

# 概要
PDF に文字として入っている個人情報を、ファイルの中身ごと削除するスクリプトです。黒塗りを重ねるだけではなく文字データ自体を消し、作成者名などのメタデータも空にします。元のファイルは変更せず、出力フォルダに forAI_元のファイル名.pdf として保存します。
```
作業フォルダ/
├── deletename_pdf.py
├── datalist.txt   ← 消したい文字列のリスト
├── before/        ← 元の PDF
└── after/         ← 処理後の PDF（なければ自動作成）
```
# 準備
初回だけ、必要なライブラリを入れます。
```
pip install pymupdf
```
消したい文字列を datalist.txt に1行に1つずつ書きます。
```
# 氏名
山田太郎
山田 太郎
Yamada Taro

# 連絡先
taro@example.com
090-1234-5678
```
• カッコや " は付けず、消したい文字をそのまま書く
• 空行と \# で始まる行は無視される（メモ用）
• スペースの有無などの表記ゆれは、それぞれ別の行に書く
• 文字コードは UTF-8 で保存する（ANSI だとエラーになる）
# 実行コマンド
作業フォルダで、python deletename_pdf.py 入力 出力フォルダ -f datalist.txt の形で実行します。
1ファイルだけ処理する（→ after\forAI_資料.pdf）:
```
python .\deletename_pdf.py .\before\資料.pdf .\after\ -f .\datalist.txt
```
before 内の PDF をまとめて処理する:
```
python .\deletename_pdf.py .\before\ .\after\ -f .\datalist.txt
```
その回だけ追加で消したいものは -t "文字列" で足せます（-t の後ろには必ず文字列を書く）:
```
python .\deletename_pdf.py .\before\ .\after\ -f .\datalist.txt -t "学籍番号1234567"
```
オプション：
-f ファイル名
ファイルに書いた文字列をすべて消す
-t "文字列"
その文字列を消す（複数並べられる）
--no-fill
黒塗りせず空白にする
# 注意点
• 実行後に [OK] と出れば、指定した文字列は残っていない。[!] が出たら、表示された箇所の表記ゆれを datalist.txt に足して再実行する
• datalist.txt に書いていない書き方（ふりがな、ローマ字、ハイフンなしの電話番号など）は消えない
• スキャンした PDF など、文字が画像になっているページは消せない（該当ページ番号が表示される）
• 仕上げに、PDF ビューアで Ctrl+F 検索して何もヒットしないことを確認する
