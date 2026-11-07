# 編排範例（ManimCE 0.22）

每個檔案只有一個 Scene，30～80 行，無旁白、無外部素材、使用明確秒數。
示範的是物件關係與連續性，並非完整課程或對原片的仿製。

在專案根目錄單獨渲染：

```sh
PATH="$HOME/Library/TinyTeX/bin/universal-darwin:$PATH" PYTHONPATH=src \
  .venv/bin/python -m manim -ql \
  src/anytomanim/guides/recipes/r01_only_move_what_changes.py OnlyMoveWhatChanges
```

已安裝套件時也可直接 `manim -ql 檔案.py 類別名`。
`anytomanim export-guides DIR` 會連同本目錄、分鏡 schema 一起匯出。

| 卡 | 檔案／類別 | 新題材與觀察重點 |
|---|---|---|
| 1 只動變的部分 | [r01_only_move_what_changes.py](r01_only_move_what_changes.py) · `OnlyMoveWhatChanges` | 一次方程；只有 +3 移到右邊成 −3，三個錨點不動 |
| 2 框住來源，再帶到結果 | [r02_box_source_to_result.py](r02_box_source_to_result.py) · `BoxSourceToResult` | 拋物線代入；來源框留著，複製框就位後才出現 9 |
| 3 結論放大，其他退下 | [r03_enlarge_conclusion.py](r03_enlarge_conclusion.py) · `EnlargeConclusion` | 等比級數；舊推導壓暗，結論放大、閃框並保留三秒 |
| 4 舊式退到角落，新式接上 | [r04_park_old_equation.py](r04_park_old_equation.py) · `ParkOldEquation` | 行列式；低亮度通式留在左下，複製展開並框出主對角乘積 |
| 5 數量邊長邊數 | [r05_count_as_it_grows.py](r05_count_as_it_grows.py) · `CountAsItGrows` | 六個結果逐個選取；整數讀值和框同步增加，總計三秒 |
| 6 鏡頭讓出空間 | [r06_camera_makes_room.py](r06_camera_makes_room.py) · `CameraMakesRoom` | 拋物線斜率問題；MovingCameraScene 下緣固定拉遠，上方新增問題 |
| 7 顏色跟著意思走 | [r07_color_follows_meaning.py](r07_color_follows_meaning.py) · `ColorFollowsMeaning` | 勾股定理；三條邊、貼近邊的標籤、平方項共用配色 |
| 8 舊的量留在新圖裡 | [r08_embed_old_quantity.py](r08_embed_old_quantity.py) · `EmbedOldQuantity` | 數線擴為座標平面；沿用原來 x 軸與點 2，標成 (2,0) |
| 9 岔開一下，再回到原處 | [r09_detour_and_return.py](r09_detour_and_return.py) · `DetourAndReturn` | 面積與剪切；save_state → 暫時剪切 → Restore，回復後才繼續 |
| 10 例子長成一般式 | [r10_example_to_general.py](r10_example_to_general.py) · `ExampleToGeneral` | 等長單位相加；四段長度 → 省略號、n 段與 nd，保留重複結構 |
| 11 比較時基準不動 | [r11_keep_comparison_baseline.py](r11_keep_comparison_baseline.py) · `KeepComparisonBaseline` | 三種拋物線曲率；相同座標尺度，藍色基準一直在場 |
| 12 把乘積拆成長和寬 | [r12_product_as_dimensions.py](r12_product_as_dimensions.py) · `ProductAsDimensions` | 矩形面積；複製一格、標 w 和 h、放回去得到 4wh |
| 13 先看一個，再放回全部 | [r13_one_then_whole.py](r13_one_then_whole.py) · `OneThenWhole` | 公平硬幣試驗；聚焦一次、說明正反機率、復原全部六次 |
| 14 調一個值，看結果跟著變 | [r14_parameter_drives_result.py](r14_parameter_drives_result.py) · `ParameterDrivesResult` | y=ax²；同一 tracker 驅動讀值、曲線和 x=1 的標記 |

只新增三個跨範例工具：`copy_box_to`（2、4）、`tracker_readout`（5、14）、
`park_in_corner`（4；可重複用於保留舊結果）。沿用既有
`spotlight/unspotlight`（3、13）、`widen_view`（6）；
其餘直接使用 CE 原語，不再包裝 `TransformFromCopy`、`Restore` 或 `Brace`。

卡片內容取自本機 `AnyToManim-bench/3b1b/cards/build.py`，證據與限制見
`cards/mining/{continuity,concrete}.json`；僅參照編排規律，數學內容及程式自行重寫。
卡 8、14 的原始卡片仍屬待確認規律，本範例不把示範當成學習成效證據。
