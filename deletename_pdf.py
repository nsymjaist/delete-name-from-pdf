"""
PDF から指定した文字列を「本当に」削除する墨消しスクリプト（PyMuPDF 使用）

- 黒塗りを上に重ねるだけでなく、ページ内部のテキストデータ自体を削除します
- 作成者名などのメタデータ（Info / XMP）も削除します
- 処理後のファイルを読み直し、文字列が残っていないか自動チェックします

使い方:
    pip install pymupdf
    python redact_pdf.py 入力 出力フォルダ -t "消したい文字列" [-t "消したい文字列" ...]

    python redact_pdf.py before/資料.pdf after/ -t "山田太郎" -t "taro@example.com"
        → after/forAI_資料.pdf として保存
    python redact_pdf.py before/ after/ -t "山田太郎"
        → before 内の PDF をすべて処理し、after/forAI_○○.pdf として保存
    python redact_pdf.py before/資料.pdf after/ -f terms.txt
        → 消したい文字列を1行に1つずつ書いたファイルで指定
    --no-fill を付けると黒塗りせず空白にします

出力フォルダがなければ自動で作ります。元のファイルは変更しません。
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

try:
    import pymupdf  # PyMuPDF 1.24 以降
except ImportError:
    try:
        import fitz as pymupdf  # 古い PyMuPDF
    except ImportError:
        sys.exit("PyMuPDF が見つかりません。先に `pip install pymupdf` を実行してください。")


def normalize(s: str) -> str:
    """全角/半角の違いと空白・改行を無視して比較するための正規化"""
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", "", s).lower()


def load_terms(args) -> list[str]:
    terms = list(args.term or [])
    if args.file:
        for line in Path(args.file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                terms.append(line)
    # 全角/半角の両方の表記で探す（例: ＡＢＣ と ABC）
    expanded = []
    for t in terms:
        for v in (t, unicodedata.normalize("NFKC", t)):
            if v and v not in expanded:
                expanded.append(v)
    return expanded


def redact(src: Path, dst: Path, terms: list[str], fill: bool) -> None:
    doc = pymupdf.open(src)
    if doc.needs_pass:
        doc.close()
        raise ValueError("パスワード付きの PDF です。パスワードを外してから実行してください。")

    total_hits = 0
    pages_without_text = []

    for page in doc:
        if not page.get_text().strip():
            pages_without_text.append(page.number + 1)

        hits = 0
        for term in terms:
            for rect in page.search_for(term):
                page.add_redact_annot(rect, fill=(0, 0, 0) if fill else None)
                hits += 1

        # 注釈（コメント・付箋など）の中身に含まれる場合はその注釈ごと削除
        for annot in list(page.annots() or []):
            if annot.type[0] == pymupdf.PDF_ANNOT_REDACT:
                continue
            content = " ".join(str(v) for v in annot.info.values())
            if any(normalize(t) in normalize(content) for t in terms):
                page.delete_annot(annot)
                hits += 1

        if hits:
            # ここで実際にテキストデータが削除される
            page.apply_redactions()
            total_hits += hits
            print(f"  ページ {page.number + 1}: {hits} 箇所を削除")

    # しおり（目次）のタイトルに含まれる場合は差し替え
    toc = doc.get_toc(simple=False)
    changed = False
    for entry in toc:
        if any(normalize(t) in normalize(entry[1]) for t in terms):
            entry[1] = "（削除）"
            changed = True
    if changed:
        doc.set_toc(toc)
        print("  しおりのタイトルを差し替えました")

    # メタデータ（作成者・タイトル・作成ソフト等）と XMP を全削除
    doc.set_metadata({})
    doc.del_xml_metadata()

    if doc.embfile_count():
        print(f"  ※ 添付ファイルが {doc.embfile_count()} 個あります。中身は検査していないので削除します")
        for name in doc.embfile_names():
            doc.embfile_del(name)

    # garbage=4 で使われなくなった古いデータも完全に除去して新規保存
    doc.save(dst, garbage=4, deflate=True, clean=True)
    doc.close()

    print(f"\n合計 {total_hits} 箇所を削除しました → {dst}")
    if pages_without_text:
        print(
            "※ 次のページは文字データがありません（スキャン画像の可能性）。"
            f"画像内の文字はこのスクリプトでは消せません: {pages_without_text}"
        )


def verify(dst: Path, terms: list[str]) -> bool:
    """出力ファイルを読み直して、文字列が残っていないか確認"""
    doc = pymupdf.open(dst)
    found = []
    for page in doc:
        text = normalize(page.get_text())
        for t in terms:
            if normalize(t) in text:
                found.append(f"ページ {page.number + 1} の本文: {t}")
        for annot in page.annots() or []:
            content = normalize(" ".join(str(v) for v in annot.info.values()))
            for t in terms:
                if normalize(t) in content:
                    found.append(f"ページ {page.number + 1} の注釈: {t}")
    meta = normalize(" ".join(str(v) for v in doc.metadata.values() if v))
    for t in terms:
        if normalize(t) in meta:
            found.append(f"メタデータ: {t}")
    doc.close()

    if found:
        print("\n[!] まだ残っている可能性がある箇所:")
        for f in found:
            print("   -", f)
        print("   表記ゆれ（スペースの有無・改行での分割など）を -t で追加して再実行してください。")
        return False
    print("\n[OK] 確認: 出力ファイルから指定した文字列は見つかりませんでした。")
    return True


PREFIX = "forAI_"


def main():
    p = argparse.ArgumentParser(description="PDF から個人情報の文字列を墨消し（完全削除）します")
    p.add_argument("input", type=Path, help="編集前の PDF ファイル、または PDF を入れたフォルダ")
    p.add_argument("out_dir", type=Path, help="編集後の PDF を保存するフォルダ（なければ自動作成）")
    p.add_argument("-t", "--term", action="append", help="削除する文字列（複数指定可）")
    p.add_argument("-f", "--file", help="削除する文字列を1行ずつ書いたテキストファイル")
    p.add_argument("--no-fill", action="store_true", help="黒塗りせず空白にする")
    args = p.parse_args()

    src_path, out_dir = args.input.resolve(), args.out_dir.resolve()
    if src_path.is_dir():
        pdfs = sorted(f for f in src_path.iterdir()
                      if f.is_file() and f.suffix.lower() == ".pdf" and not f.name.startswith(PREFIX))
        if not pdfs:
            sys.exit(f"{src_path} に PDF が見つかりません。")
    elif src_path.is_file():
        pdfs = [src_path]
    else:
        sys.exit(f"ファイルまたはフォルダが見つかりません: {args.input}")
    if out_dir.exists() and not out_dir.is_dir():
        sys.exit(f"出力先はフォルダを指定してください: {args.out_dir}")

    terms = load_terms(args)
    if not terms:
        sys.exit("削除する文字列を -t か -f で指定してください。")

    out_dir.mkdir(parents=True, exist_ok=True)
    failed = []
    for src in pdfs:
        dst = out_dir / (PREFIX + src.name)
        print(f"\n===== {src.name} =====")
        try:
            redact(src, dst, terms, fill=not args.no_fill)
            if not verify(dst, terms):
                failed.append(src.name)
        except Exception as e:  # 1つ失敗しても残りは続ける
            print(f"[エラー] {e}")
            failed.append(src.name)

    print(f"\n----- 完了: {len(pdfs)} 件中 {len(pdfs) - len(failed)} 件 OK → {out_dir}")
    if failed:
        print("要確認:", ", ".join(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
