# LWM's Fuel Filter Fix

RimWorld 1.6 / LWM's Fuel Filter (Continued) 向けの独立した修正パッチModです。

燃料フィルタに画面上は非表示の非対応項目が保存されると、木材・原木を許可していても補給できなくなる問題を回避します。設備本来の対応燃料とユーザーの許可設定の両方を満たす運搬可能な物だけを探索します。保存済みフィルタの書き換えや依存Modの上書きは行いません。

## 必要Mod・導入

- Harmony (`brrainz.harmony`)
- LWM's Fuel Filter (Continued) (`zal.lwmfuelfilter`, Workshop 3288440994)
- このModをLWM's Fuel Filterの後に配置してください。

通常補給と一括補給の燃料探索を対象にします。到達可能性・予約・持出禁止・必要個数の判定はゲーム本体の探索処理を利用します。

## 原因と修正範囲

本体のカテゴリ一括選択は、親フィルタで非表示のDefも許可リストに追加できる処理です。LWMの貼り付け処理も対応燃料との照合を行いません。非運搬対象の建築物を含むフィルタでは`BestThingRequest`が`Everything`になり、`ClosestThingReachable`が探索を中断します。

本Modは`RefuelWorkGiverUtility.FindBestFuel`と`FindAllFuel`をHarmony Prefixで置き換え、運搬可能な候補に対して元の対応燃料フィルタと個別フィルタの両方を検査します。HP・品質・特殊条件も`Allows(Thing)`経由で保持します。LWMの個別フィルタがない設備では元処理へ戻ります。

今回のセーブで最初に不正な項目が混入した操作は未特定です。この修正はカテゴリ選択UI自体や、表示と保存リストの不一致を修正するものではありません。

## 検証状況

- 依存先: RimWorld 1.6.4871、LWM's Fuel Filter (Continued) 1.1.2。
- `Tests`は実ゲームDLLの`ThingFilter`のDef許可リストと探索要求生成を使い、不正な探索要求の再現・Def単位の許可/拒否・フィルタを変更しないことを検査します。Unityを起動しないためThingDefは必要なフィールドだけを設定し、`Allows(Thing)`はDef判定に限定したテスト用派生型に置き換えています。HP・品質・特殊条件は単体テスト対象外です。
- 隔離されたRimWorldLinux 1.6実機で、焚き火・木材・ポーンを用いた補給テスト9項目がVanilla構成でPASS。非表示の非運搬項目混入を再現し、探索・補給ジョブ生成・開始・完了を確認しました。
- Medieval Overhaul併用構成でも補給テスト9項目はPASS。ただし、SYR単独でも再現するFMOD音声エラーが起動時に2件あり、厳格なログ正常性判定は未通過です。
- 一括補給ジョブそのものの完了、複数ポーン間の予約競合、セーブ再読込、各種特殊条件などは未検証。詳細な実行ログと残課題は[VALIDATION.md](VALIDATION.md)を参照してください。
- Steam Workshop未公開。公開前候補として継続検証中です。

## English

An independent patch for **RimWorld 1.6** and **LWM's Fuel Filter (Continued)**. Hidden unsupported entries in a saved fuel filter can make refueling fail despite available fuel. This mod searches haulable items and requires both the building's original fuel filter and the user's individual filter to accept each candidate.

Requires Harmony and LWM's Fuel Filter (Continued); load after both. Normal and atomic refueling are covered. Saved filters are not rewritten, and user-disabled fuels remain disabled. The category-selection UI itself is not changed.

The category checkbox can select hidden descendants; unrestricted filter pasting is another possible entry point. A non-haulable building in the filter can produce an `Everything` request, which the game's reachable search rejects. The first action that polluted the investigated save is unknown.

Real-game isolated RimWorld 1.6 Quickstart now passes 9/9 checks in Vanilla, including an actual pawn completing a campfire refuel job with a polluted fuel filter. The same nine functional checks pass with Medieval Overhaul, but that environment has two pre-existing SYR/MO FMOD startup errors, so a strict clean-log PASS has not been established. Atomic refuel job completion, save/reload, competing reservations and further compatibility remain untested; see [VALIDATION.md](VALIDATION.md). Pre-release; no Workshop publication yet.

## Build / tests

Install a .NET SDK. Defaults assume this Mod is under `RimWorld/Mods` and Workshop is in the standard adjacent directory. Game and third-party DLLs are not distributed here.

```powershell
dotnet build Source/LWMsFuelFilterFix.csproj -c Release -p:UseSharedCompilation=false
dotnet build Tests/LWMsFuelFilterFix.Tests.csproj -c Release -p:UseSharedCompilation=false
& ./Tests/bin/Release/net48/LWMsFuelFilterFix.Tests.exe 'D:\SteamLibrary\steamapps\common\RimWorld'
```

Build properties: `RimWorldDir`, `WorkshopDir`, `HarmonyDll`, `FuelFilterDll`. Target: .NET Framework 4.8, matching the installed LWM assembly. Only this project's DLL belongs in `1.6/Assemblies`.

## Credits / license

Original LWM's Fuel Filter: Little White Mouse. Continued version: Zaljerem. This independent patch: sucRo. MIT license; see [LICENSE](LICENSE).
