# 萬象拼音繁體方案

手動建置 [rime-wanxiang / wanxiang](https://github.com/amzxyz/rime-wanxiang/tree/wanxiang)，搭配 [RIME-LMDG / dicts_hant](https://github.com/amzxyz/RIME-LMDG/tree/wanxiang/dicts_hant) 官方繁體詞庫與 `wanxiang-lts-zh-hant.gram`。

在 Actions 選擇 **Build wanxiang-base-hant → Run workflow → main**。沒有每日排程。建置完成後會提交生成檔案到 main，並發布兩個 ZIP。Release 使用 `v版本-hant.執行次數.重試次數`，避免改寫舊版標籤及附件。

- `rime-wanxiang-base.zip`：不含語言模型，需另外下載 [繁體模型](https://github.com/amzxyz/RIME-LMDG/releases/download/LTS/wanxiang-lts-zh-hant.gram)。
- `rime-wanxiang-full.zip`：包含繁體模型。

解壓至 Rime 使用者目錄並重新部署。已內建繁體設定，預設臺灣字形，可切換通繁、簡體、港繁。請先備份個人設定，移除舊版 `super_replacer/rules/@3` 等繁體補丁，以免覆蓋新設定。既有使用者詞庫不會自動轉換。

## 建置方式

`.github/scripts/build_hant.py` 保留官方繁體主詞庫。若官方繁體目錄缺少新版 `abbrev`、`t9_abbrev`，只將上游簡碼詞典的文字欄轉繁，保留編碼及詞頻。保留 OpenCC JSON，編譯所有引用的 `.ocd2`；保留 LICENSE。

`custom_configs/zi.dict.新增部分.yaml` 會追加至字表；`custom_configs/修改TWVariants.txt` 保留原有「重複行移除、不同行新增」規則。這些檔案沿用 v17.10.3。

保留上游 `wanxiang.schema.yaml`、`wanxiang_t9.schema.yaml`、`wanxiang_t9i.schema.yaml` 與 `default.yaml` 原檔。繁體設定由建置程式產生在根目錄的 `wanxiang.custom.yaml`、`wanxiang_t9.custom.yaml`、`wanxiang_t9i.custom.yaml` 及 `default.custom.yaml`。方案補丁亦同步至 `custom/` 模板，供切換輸入方案使用。發布包包含這些補丁；安裝前請備份並合併個人 custom 設定。

每次抓取兩個上游的 wanxiang 分支最新快照，`build-info.json` 記錄實際提交。建置腳本先檢查字典、附屬方案與 OpenCC 依賴；有缺漏就停止，不發布不完整套件。修改腳本後仍應以實際 Rime 重新部署、測試候選與切換行為。

OpenCC 標準轉換詞典優先沿用萬象已有檔案；缺少的 `STCharacters`、`STPhrases`、`TSCharacters`、`TSPhrases`、`HKVariants`、`TWVariants` 從 [OpenCC 官方文字詞典](https://github.com/BYVoid/OpenCC/tree/master/data/dictionary) 補齊，清除註解及空行後以 `opencc_dict` 編譯為 `.ocd2`。臺灣字形客製在編譯前套用；emoji 等萬象專用詞典仍由萬象提供。
