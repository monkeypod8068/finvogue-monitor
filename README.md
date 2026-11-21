# マーケット・ストレス・モニター

FinVogue に埋め込んで表示する公開ページです。

- `index.html` … 表示用のページ(固定)。「分析」「朝版レポート」「夕方版レポート」のタブ構成。`#morning` `#evening` で直接開けます。
- `report_morning.html` / `report_evening.html` … 元のHTMLレポート(朝版・夕方版)。分析タスクが crash-monitor からコピーします。
- `latest.json` … 最新の判定と分析。Claudeの定期実行タスクが朝・夕方に上書きします。
- `archive/` … 過去の `latest.json` の保存。

本ページは投資助言ではありません。
