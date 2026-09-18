# 萬象拼音繁體方案

手動建置 [rime-wanxiang / wanxiang-base](https://github.com/amzxyz/rime-wanxiang/tree/wanxiang-base)，搭配 [RIME-LMDG / dicts_hant](https://github.com/amzxyz/RIME-LMDG/tree/wanxiang/dicts_hant) 官方繁體詞庫與 `wanxiang-lts-zh-hant.gram`。

在 Actions 選擇 **Build wanxiang-base-hant → Run workflow → main**。每天 UTC 00:00（臺北時間 08:00）也會執行建置。建置完成後會提交生成檔案到 main，並發布兩個 ZIP。Release 標籤使用 `v版本`，名稱為 `v版本 Rime万象拼音输入方案-繁體詞庫`；同版本再次發布會更新同一個 Release 及同名附件。若 `custom_configs/wanxiang.custom.yaml` 或 `custom_configs/default.custom.yaml` 相對於 `custom-configs` 標籤有變更，流程也會更新該補丁 Release。

- `rime-wanxiang-base.zip`：不含語言模型，需另外下載 [繁體模型](https://github.com/amzxyz/RIME-LMDG/releases/download/LTS/wanxiang-lts-zh-hant.gram)。
- `rime-wanxiang-full.zip`：包含繁體模型。

解壓至 Rime 使用者目錄，另行套用個人繁體 custom 設定後重新部署。請先備份並合併個人設定，移除舊版 `super_replacer/rules/@3` 等繁體補丁，以免覆蓋新設定。既有使用者詞庫不會自動轉換。

## 建置方式

主目錄的方案與資料檔以 `wanxiang-base` 分支為來源；上游目錄僅複製 `lua/`、`opencc/`、`custom/`，`dicts/` 使用官方繁體詞庫，不包含 `plum/`。另保留本專案的建置設定、自訂來源與版本紀錄。

`.github/scripts/build_hant.py` 保留官方繁體主詞庫。若官方繁體目錄缺少新版 `abbrev`、`t9_abbrev`，只將上游簡碼詞典的文字欄轉繁，保留編碼及詞頻。保留 OpenCC JSON，編譯所有引用的 `.ocd2`；保留 LICENSE。

`custom_configs/zi.dict.新增部分.yaml` 會追加至字表；`custom_configs/修改TWVariants.txt` 保留原有「重複行移除、不同行新增」規則。這些檔案沿用 v17.10.3。

保留上游 schema 與 `default.yaml` 原檔。個人 `.custom.yaml` 統一存放於 `custom_configs/`，不複製到主目錄，也不自動產生或放入發布包的主目錄。`custom/` 保持上游原始模板，不改寫。需要個人繁體設定時，請自行將所需補丁放入 Rime 使用者目錄。

每次抓取方案上游的 `wanxiang-base` 分支及 RIME-LMDG 的 `wanxiang` 分支最新快照，`build-info.json` 記錄實際提交。建置腳本先檢查字典、附屬方案與 OpenCC 依賴；有缺漏就停止，不發布不完整套件。修改腳本後仍應以實際 Rime 重新部署、測試候選與切換行為。

OpenCC 標準轉換詞典優先沿用萬象已有檔案；缺少的 `TSCharacters`、`TSPhrases`、`HKVariants`、`TWVariants` 從 [OpenCC 官方文字詞典](https://github.com/BYVoid/OpenCC/tree/master/data/dictionary) 補齊，清除註解及空行後以 `opencc_dict` 編譯為 `.ocd2`。臺灣字形客製在編譯前套用；emoji 先解碼為文字、轉繁，再編譯回 `.ocd2`。編譯後刪除中間 TXT，僅調整建置結果中的 JSON 引用，`custom_configs/` 原檔不變。缺少 `Custom_TSPhrases.txt` 時由 `Custom_STPhrases.txt` 的對照反向建立，保留 `Custom_TSPhrases.txt` 與 `Custom_Emoji.txt`；移除 `Custom_STPhrases.txt` 及 `STPhrases`、`STCharacters` 的文字檔與 `.ocd2`。
