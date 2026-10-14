# Regulated gauges: unresolved / excluded candidates

Companion to `climate_core/catalog/data/regulated_gauges.csv` (compiled 2026-10-14). The curated list is not exhaustive; sites below were considered plausibly regulated but could not be verified against a retrieved source (or were deliberately left out), so they are NOT tagged. Absence from the CSV means "not known to be regulated", not "unregulated".

Primary evidence used: USGS Water Resources Data reports for water year 2004 (Oregon, Idaho vols. 1-2, Washington) station `REMARKS`, retrieved from pubs.usgs.gov; supplemented by a few agency/project pages. Stations not published in those 2004 reports (many tailwater, canal, drain and newer sites) therefore had no gauge-level remark available.

## RESOLVED 2026-10-14 (anchor discrepancy)
Resolution: the Orofino row (13340000) was removed from the data file and the anchor changed to 13341000 (NF Clearwater at Ahsahka, below Dworshak Dam) by user decision. Orofino is upstream of the Dworshak-regulated North Fork and reads as not regulated; it is not listed. Original note follows.

- **13340000 Clearwater R at Orofino** is an anchor and is included (confidence `medium`, regulator text flagged UNVERIFIED), but the evidence contradicts the premise. Orofino lies on the main stem upstream of the North Fork confluence at Ahsahka; drainage area 5,507 sq mi, versus 7,976 sq mi at Peck, which the WDR says is "regulated by Dworshak Reservoir 5.1 mi upstream". The WY2004 WDR remark for 13340000 contains no regulation statement and the USGS HCDN page lists "Storage: 0.00%". The regulated Clearwater gauges are 13341000 (NF Clearwater at Ahsahka), 13341050 (Peck) and 13342500 (Spalding), all included as `high`. Recommend replacing the anchor/test with one of those unless a source for Orofino turns up.

## Unverified: no gauge-level source retrieved
| site_no | name | reason |
|---|---|---|
| 11504260, 11504290, 11509105, 11509200, 11509250, 11509340, 11508700, 11504115, 11492550, 11493100 | Klamath Project canals/drains, Wood River, Sand/Scott Cr canal sites | Plausibly diversion/canal flows (Reclamation Klamath Project) but not in the 2004 WDR; no page retrieved |
| 11511990 | Klamath R ab Fall Cr | Below JC Boyle / Copco; no remark retrieved |
| 11502500 | Williamson R blw Sprague | WDR says only "some regulation by diversion dams and log pond operations": too weak |
| 12058790 | NF Skokomish nr Lwr Cushman Dam | Tacoma Power project page returned 404 |
| 12089208 | Centralia Power Canal near McKenna | Remark matched to this id was ambiguous; not used |
| 12088000 | Ohop Creek nr Eatonville | WDR remark ("regulated by headworks") could not be reliably attributed to this id |
| 12092000, 12096500 | Puyallup R nr Electron / Alderton | Electron diversion upstream, but WDR remark for 12092000 states no regulation |
| 12097850, 12100490-12100498, 12100500, 12101100, 12101102 | White R below Mud Mountain / Lake Tapps diversion sites | Not in retrieved 2004 report with usable remark |
| 12179000, 12180300, 12183900, 12184700, 12184800, 12189700, 12178600, 12178900 | Skagit R gauges between Newhalem and Rockport | Upstream Seattle City Light dams, but not published in the retrieved report |
| 12190400, 12193400 | Baker R gauges | Puget Sound Energy Baker project page retrieved did not mention the gauge/Concrete |
| 12398560 vs 12426000 | see CSV | Included only at the level the retrieved project page supports |
| 12415500, 12417650, 12422000 | Coeur d'Alene Lake / Spokane R at Blackwell / below N Greene St | Post Falls Dam (Avista) clearly regulates; no gauge-level source retrieved |
| 12442500 | Similkameen R nr Nighthawk | Remark describes only natural diversion to Palmer Lake |
| 12452550 | Chelan R at Habitat 4 channel | No source |
| 12502500, 12506000, 12507573 | Ahtanum Cr, Toppenish Cr, Yakima R at RM 73.8 | Irrigation-affected; remarks do not state regulation |
| 12404500, 12401500 | Kettle R | Remarks describe only small irrigation diversions |
| 14128600 | Columbia R at Stevenson | No remark retrieved (certainly regulated; mainstem) |
| 13011000, 13013650, 13018750, 13022500 | Snake R Moran/Moose/Flat Cr/above Palisades | Jackson Lake Dam upstream; WDR remark for 13011000 lacks a regulation statement |
| 13050500, 13052200, 13055000, 13055340, 13058510, 13057940, 13058000 | Henrys Fork/Teton/Willow Cr | Remarks mention only irrigation diversions or ambiguous attribution |
| 13115000 | Mud Lake | Pumped irrigation diversion from perched lake: kind unclear |
| 13139510, 13140335, 13140800 | Big Wood R (Hailey to Stanton) | Remarks state only irrigation diversions |
| 13130300, 13132100, 13132373 | Big Lost R | Below Mackay Reservoir but no remark retrieved |
| 13192200, 13206305, 13206400, 13210045, 13210810, 13210824, 13210831, 13210980, 13210986, 13211205, 13211210, 13212549, 13212890, 13213000, 13213072 | Lower Boise R, drains and canals | Regulated/return-flow dominated (IDWR WD63 accounting) but no gauge-level source retrieved; WDR remark for 13213000 has no regulation statement |
| 13305000, 13305310, 13302005, 13302500 | Salmon basin (Lemhi, Pahsimeroi) | Irrigation diversions only; no regulation statement |
| 14139940, 14140000 | Bull Run R below Reservoir 2 / river only | Remark for these ids not retrievable or ambiguous |
| 14335072 | Rogue R at Cole Rivers Hatchery | Below Lost Creek Dam; no remark retrieved |
| 14240311, 14240525, 14242580 | Spirit Lake tunnel outlet, NF Toutle below SRS, Toutle R | Managed outlets/sediment structure; no regulation statement (14242580 WDR says none) |
| 14070621, 14070900 | Bend diversion canal / Bridge Cr | Municipal diversion; no source |
| 14120000 | Hood R at Tucker Br | WDR notes irrigation diversions only |
| 14123500 | White Salmon R nr Underwood | WDR regulation text refers to Condit Dam, removed 2011-12 |
| 12045500 | Elwha R at McDonald Br | Elwha dams removed 2011-14 |
| 14015350, 14013700, 14013000 | Mill Cr (Walla Walla) | WDR says no regulation upstream (municipal diversion only) |

## Excluded for weak evidence (kept out deliberately)
Gauges whose WDR remark states only "minor", "slight" or "possible" regulation, or only irrigation diversions, were left out to avoid over-tagging, including: 12031000, 12093500, 12117500, 12119000, 12148500, 12061500, 12445000, 12395000, 13037500, 13038500, 13049500, 13055250, 13057155, 13060000, 13092747, 13159800, 13168500, 13258500, 13266000, 13333000, 13233300, 14015000, 14033500 (Umatilla R nr Umatilla; McKay Reservoir, "some regulation" plus large diversions: reasonable candidate to add), 14137000, 14138720, 14138850, 14138900, 14226500, 14231000, 14312000, 14314500, 14315950, 14319500, 14330000, 14332000, 14357500, 14164700.

## Notes on included `medium` rows
- 13340000: see above.
- 12426000 (Nine Mile Dam) and 12453690 / 12462560 (Chelan PUD tailwater unit gauges): the retrieved FERC-summary pages (hydroreform.org) establish that the dams exist on the river and operate run-of-river/peaking, not that the gauge is regulated; evidence is dam-upstream/at-gauge only.
- Yakima, Bear River, Crab Creek rows: USGS remark says flow is "affected"/"partly regulated" by reservoirs and diversions.
