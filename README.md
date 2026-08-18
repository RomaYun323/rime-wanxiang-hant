## rime-wanxiang-万象拼音-自用繁體方案
方案原作者https://github.com/amzxyz



僅根據個人輸入習慣修改繁體方案
## 修改內容

- 新增繁體方案補丁`wanxiang.custom.yaml`, 聯絡人詞庫`contacts.dict.yaml`
- `wanxiang.dict.yaml`新增`- contacts`聯絡人詞庫，無此需求者手動刪除該行
- `zi.dict.yaml`新增內容參考[zi.dict.新增部分](https://github.com/RomaYun323/rime-wanxiang-hant/blob/main/custom_configs/zi.dict.%E6%96%B0%E5%A2%9E%E9%83%A8%E5%88%86.yaml)
- `TWVariants.txt`新增移除內容參考[修改TWVariants.txt](https://github.com/RomaYun323/rime-wanxiang-hant/blob/main/custom_configs/%E4%BF%AE%E6%94%B9TWVariants.txt)，移除重複行新增不同行
- 從[RIME-LMDG](https://github.com/amzxyz/RIME-LMDG)取得繁體詞庫`dicts_hant.zip`及繁體大模型語法包`wanxiang-lts-zh-hant.gram`
- OpenCC `s2t.json`轉換`abbrev.txt`, `chengyu.txt`, `chinese_english.txt`, `emoji.txt`, `english_chinese.txt`, `others.txt`, `t9_abbrev.txt`, `tips_show.txt`, `number_translator.lua`, `shijian.lua`
- 從[OpenCC](https://github.com/byvoid/opencc)取得`TSPhrases.txt`, `TSCharacters.txt`


