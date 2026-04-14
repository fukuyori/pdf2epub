# pdf2epub

スキャンPDFや通常の文字レイヤー付きPDFを EPUB に変換するための Python CLI です。

主な機能:

- 文字レイヤー付き PDF から本文テキストを抽出
- ページ画像を EPUB に埋め込み
- 固定レイアウト EPUB として各ページを出力
- `右閉じ/左閉じ` を `auto / rtl / ltr` で指定
- `--layout fixed / reflow` で固定レイアウトかリフロー型かを切り替え
- `titles.txt` の候補辞書と `PDFメタデータ / 表紙OCR` を照合してタイトルを推定
- `PDFメタデータ / 表紙OCR` から `巻・号数` を抽出して EPUB メタデータと出力名に反映
- 1ページ目を EPUB の表紙画像として登録
- 目次ページを検出できた場合は、抽出した目次をまとめたページを EPUB に追加
- PDF の文字レイヤーが空のページでは、`tesseract` が入っていれば OCR フォールバック可能

向いている用途:

- スキャンPDFを見た目に近いまま EPUB 化したい
- 通常PDFをページ単位で EPUB にまとめたい

注意:

- `--layout reflow` を選んでも、PDF の段落構造や見出し構造を再構成する実装ではありません。
- 一般的なリフローEPUBのように本文を作り直す用途より、ページ単位で保持したい用途に向いています。

## セットアップ

### pip 版

```bash
pip install -e .
```

### uv 版

```bash
uv sync
```

`PyMuPDF` が必要です。Tesseract OCR を使う場合は別途 `tesseract` コマンドをインストールしてください。

## 使い方

### 変換

#### pip 版

```bash
pdf2epub convert ".\input\週刊少年サンプル 2026年04月号.pdf" --binding auto --ocr-mode auto
```

#### uv 版

```bash
uv run pdf2epub convert ".\input\週刊少年サンプル 2026年04月号.pdf" --binding auto --ocr-mode auto
```

通常の文字レイヤー付き PDF の例:

```bash
uv run pdf2epub convert ".\input\manual.pdf" --ocr-mode pdf-text --layout reflow
```

スキャン中心の PDF の例:

```bash
uv run pdf2epub convert ".\input\scan.pdf" --ocr-mode auto --layout fixed
```

主なオプション:

- `--binding {auto,rtl,ltr}`
- `--ocr-mode {auto,pdf-text,tesseract,none}`
- `--layout {fixed,reflow}`
- `--ocr-lang jpn+eng`
- `--titles-file .\titles.txt`
- `--dpi 150`
- `--title "任意タイトル"`
- `--issue "第12巻"`
- `--author "著者名"`
- `--output-dir .\output`
- `--output-file ".\output\sample.epub"`

### 解析だけ確認

#### pip 版

```bash
pdf2epub inspect ".\input\コミック名 第12巻.pdf"
```

#### uv 版

```bash
uv run pdf2epub inspect ".\input\コミック名 第12巻.pdf"
```

### 複数ファイルをまとめて変換

#### pip 版

```powershell
Get-ChildItem .\samples\*.pdf | ForEach-Object {
    pdf2epub convert $_.FullName --output-dir .\output
}
```

#### uv 版

```powershell
Get-ChildItem .\samples\*.pdf | ForEach-Object {
    uv run pdf2epub convert $_.FullName --output-dir .\output
}
```

サブフォルダも含める場合:

```powershell
Get-ChildItem .\samples\*.pdf -Recurse | ForEach-Object {
    uv run pdf2epub convert $_.FullName --output-dir .\output
}
```

### 実行スクリプト

PowerShell 用の実行スクリプトもあります。

```powershell
.\scripts\run-pdf2epub.ps1
```

主な例:

```powershell
.\scripts\run-pdf2epub.ps1 -InputPath .\samples -OutputDir .\output
.\\scripts\\run-pdf2epub.ps1 -InputDir "D:\books\input" -OutputDir "D:\books\epub"
.\scripts\run-pdf2epub.ps1 -InputPath .\samples\科学_202510.pdf
.\scripts\run-pdf2epub.ps1 -InputPath .\samples -Recurse
.\scripts\run-pdf2epub.ps1 -InputPath .\samples\科学_202510.pdf -InspectOnly
```

指定できる主な引数:

- `-InputPath` / `-InputDir` : 単一PDFまたはPDFを含む入力フォルダ
- `-OutputDir` : EPUBの出力先フォルダ
- `-TitlesFile` : タイトル候補ファイル
- `-Binding` : `auto / rtl / ltr`
- `-OcrMode` : `auto / pdf-text / tesseract / none`
- `-OcrLang` : OCR 言語
- `-Recurse` : サブフォルダも対象にする
- `-InspectOnly` : 変換せず解析だけ行う

注意:

- 現在の PowerShell スクリプトは `--layout` 切り替えには未対応です。
- `layout` を指定したい場合は `pdf2epub convert ... --layout ...` または `uv run pdf2epub convert ... --layout ...` を直接使ってください。

出力例:

```text
Input: C:\books\sample.pdf
Suggested title: 科学
Suggested issue: 25/10
Metadata source: title-candidates
Suggested binding: rtl
Reason: filename/text heuristics suggest Japanese right-bound content
Detected TOC page: 3
Detected TOC entries: 12
Pages: 192
```

## 表紙と目次

- 表紙: 1ページ目の画像を EPUB の `cover-image` として登録します。
- 目次: 先頭付近のページから `目次 / もくじ / contents` を含むページを探し、項目が読めた場合は `detected-toc.xhtml` を生成して EPUB に追加します。

注意:

- 現在の目次生成は、抽出した項目を EPUB 内の目次ページにまとめる実装です。
- 雑誌の誌面上のページ番号と PDF ページ番号の厳密対応付けはまだしていないため、記事本文へ直接ジャンプする目次ではありません。

## タイトル辞書

`titles.txt` に候補となるタイトルを 1 行 1 件で書いておくと、PDFメタデータや表紙OCRの文字列と照合して最も近い候補を採用します。

```text
月間統計
Newton
地理
科学
統計
Interface
```

既定ではカレントディレクトリの `titles.txt` を自動で読みます。別ファイルを使う場合は `--titles-file` で指定できます。

注意:

- Python プログラムではファイル名からタイトルや号数を抽出しません。
- タイムスタンプ名のスキャンPDFでは、`titles.txt` があっても OCR で表紙文字を読めないとタイトル確定はできません。
- そのため、画像中心のPDFでは `tesseract` を入れると辞書照合が効きやすくなります。

## 綴じ方向の考え方

`auto` の場合は次を見て判定します。

- ファイル名に `右開き / 左開き / manga / novel / english` などの明示的キーワードがあるか
- ファイル名や先頭数ページのテキストに日本語が多いか

日本語主体のコミック・雑誌・文芸書を優先して `rtl` に寄せる実装です。完全自動判定は難しいため、誤判定が困る場合は `--binding rtl` または `--binding ltr` を明示指定してください。

## レイアウトの考え方

- `--layout fixed`: 既定値です。各ページを固定レイアウト EPUB として出力します。
- `--layout reflow`: 固定レイアウト宣言を付けず、通常ページとして出力します。

注意:

- `reflow` を選んでも、現在の本文構造は PDF を段落再構成する実装ではありません。
- 画像と抽出テキストをページごとに並べる形なので、一般的なリフローEPUBのような再構成とは異なります。
- 通常PDFで本文テキストを優先したい場合は `--ocr-mode pdf-text` を推奨します。
- スキャンPDFでは `--ocr-mode auto` か `--ocr-mode tesseract` を使うと OCR フォールバックが効きます。

## 出力ファイル名

既定では、出力する EPUB のファイル名は入力 PDF のファイル名と同じです。拡張子だけ `.pdf` から `.epub` に変わります。

```text
{入力ファイル名}.epub
```

例:

- `科学_202510.pdf` -> `科学_202510.epub`
- `月刊統計_202503.pdf` -> `月刊統計_202503.epub`

別名で出力したい場合は `--output-file` を指定します。

## 制限

- OCR 品質は PDF の文字レイヤー、または Tesseract の結果に依存します。
- 見開き分割や縦書き再構成は未対応です。
- 章立て抽出ではなく、ページ単位で画像と OCR テキストを格納するシンプルな EPUB です。
- 固定レイアウト宣言は付与しますが、OCR テキストは座標付きテキストレイヤーではありません。
