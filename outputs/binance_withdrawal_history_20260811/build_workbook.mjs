import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = path.resolve("outputs/binance_withdrawal_history_20260811");
const payload = JSON.parse(await fs.readFile(path.join(outputDir, "withdrawals_masked.json"), "utf8"));
const records = payload.records;
const assets = [...new Set(records.map((row) => row.coin).filter(Boolean))].sort();
const historyStartRow = 5;
const historyEndRow = historyStartRow + Math.max(records.length, 1) - 1;

function binanceDate(value) {
  if (!value) return null;
  const parsed = new Date(value.includes("T") ? value : value.replace(" ", "T") + "Z");
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
const history = workbook.worksheets.add("Withdrawal History");
const sources = workbook.worksheets.add("Sources & Notes");

for (const sheet of [summary, history, sources]) sheet.showGridLines = false;

summary.mergeCells("A1:E1");
summary.getRange("A1:E1").values = [["Binance Crypto Withdrawal History"]];
summary.getRange("A1:E1").format = {
  fill: "#0B1F3A",
  font: { bold: true, color: "#FFFFFF", size: 18 },
  verticalAlignment: "center",
};
summary.getRange("A1:E1").format.rowHeight = 34;
summary.mergeCells("A2:E2");
summary.getRange("A2:E2").values = [[
  `Read-only export retrieved ${new Date(payload.retrieved_at).toISOString().slice(0, 19).replace("T", " ")} UTC · destination addresses and transaction identifiers are masked`,
]];
summary.getRange("A2:E2").format = {
  fill: "#E8EEF7",
  font: { color: "#334155", italic: true },
  wrapText: true,
};
summary.getRange("A2:E2").format.rowHeight = 32;

summary.getRange("A4:E4").values = [["Total Records", "Completed", "Assets", "First Withdrawal", "Latest Withdrawal"]];
summary.getRange("A4:E4").format = {
  fill: "#F0B90B",
  font: { bold: true, color: "#111827" },
  horizontalAlignment: "center",
};
summary.getRange("A5:E5").formulas = [[
  `=COUNTA('Withdrawal History'!$A$${historyStartRow}:$A$${historyEndRow})`,
  `=COUNTIF('Withdrawal History'!$G$${historyStartRow}:$G$${historyEndRow},"Completed")`,
  `=COUNTA(A10:A${9 + Math.max(assets.length, 1)})`,
  `=MIN('Withdrawal History'!$A$${historyStartRow}:$A$${historyEndRow})`,
  `=MAX('Withdrawal History'!$A$${historyStartRow}:$A$${historyEndRow})`,
]];
summary.getRange("A5:C5").format = {
  font: { bold: true, size: 15, color: "#0B1F3A" },
  horizontalAlignment: "center",
};
summary.getRange("D5:E5").format.numberFormat = "yyyy-mm-dd hh:mm:ss";
summary.getRange("D5:E5").format.horizontalAlignment = "center";

summary.mergeCells("A8:E8");
summary.getRange("A8:E8").values = [["Activity by Asset"]];
summary.getRange("A8:E8").format = {
  fill: "#0B1F3A",
  font: { bold: true, color: "#FFFFFF" },
};
summary.getRange("A9:E9").values = [["Asset", "Withdrawals", "Total Amount", "Total Fees", "Completed"]];
summary.getRange("A9:E9").format = {
  fill: "#DDE6F2",
  font: { bold: true, color: "#0B1F3A" },
  borders: { preset: "outside", style: "thin", color: "#94A3B8" },
};
if (assets.length) {
  summary.getRange(`A10:A${9 + assets.length}`).values = assets.map((asset) => [asset]);
  const formulas = assets.map((_, index) => {
    const row = index + 10;
    return [
      `=COUNTIF('Withdrawal History'!$C$${historyStartRow}:$C$${historyEndRow},A${row})`,
      `=SUMIF('Withdrawal History'!$C$${historyStartRow}:$C$${historyEndRow},A${row},'Withdrawal History'!$D$${historyStartRow}:$D$${historyEndRow})`,
      `=SUMIF('Withdrawal History'!$C$${historyStartRow}:$C$${historyEndRow},A${row},'Withdrawal History'!$E$${historyStartRow}:$E$${historyEndRow})`,
      `=COUNTIFS('Withdrawal History'!$C$${historyStartRow}:$C$${historyEndRow},A${row},'Withdrawal History'!$G$${historyStartRow}:$G$${historyEndRow},"Completed")`,
    ];
  });
  summary.getRange(`B10:E${9 + assets.length}`).formulas = formulas;
  summary.getRange(`C10:D${9 + assets.length}`).format.numberFormat = "0.00000000";
  summary.getRange(`A10:E${9 + assets.length}`).format.borders = {
    insideHorizontal: { style: "thin", color: "#E2E8F0" },
    bottom: { style: "thin", color: "#94A3B8" },
  };
}
summary.freezePanes.freezeRows(2);
summary.getRange("A:E").format.columnWidth = 18;
summary.getRange("A:A").format.columnWidth = 14;

history.mergeCells("A1:N1");
history.getRange("A1:N1").values = [["Complete Binance Crypto Withdrawal Records"]];
history.getRange("A1:N1").format = {
  fill: "#0B1F3A",
  font: { bold: true, color: "#FFFFFF", size: 16 },
};
history.mergeCells("A2:N2");
history.getRange("A2:N2").values = [[
  "All records returned by Binance from 2017-07-01 through the retrieval timestamp. Sensitive address, transaction, and withdrawal identifiers are masked.",
]];
history.getRange("A2:N2").format = { fill: "#E8EEF7", font: { italic: true, color: "#334155" } };
const headers = [
  "Apply Time (UTC)", "Complete Time (UTC)", "Asset", "Amount", "Fee", "Network", "Status",
  "Transfer Type", "Wallet", "Destination (masked)", "TxID (masked)", "Withdrawal ID (masked)",
  "Client Order ID", "Info",
];
history.getRange("A4:N4").values = [headers];
history.getRange("A4:N4").format = {
  fill: "#F0B90B",
  font: { bold: true, color: "#111827" },
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: "#A67C00" },
};
history.getRange("A4:N4").format.rowHeight = 32;
if (records.length) {
  history.getRange(`A${historyStartRow}:N${historyEndRow}`).values = records.map((row) => [
    binanceDate(row.apply_time), binanceDate(row.complete_time), row.coin, row.amount, row.fee,
    row.network, row.status, row.transfer_type, row.wallet, row.destination_masked, row.txid_masked,
    row.withdrawal_id_masked, row.withdraw_order_id, row.info,
  ]);
  history.getRange(`A${historyStartRow}:B${historyEndRow}`).format.numberFormat = "yyyy-mm-dd hh:mm:ss";
  history.getRange(`D${historyStartRow}:E${historyEndRow}`).format.numberFormat = "0.00000000";
  history.getRange(`A${historyStartRow}:N${historyEndRow}`).format.borders = {
    insideHorizontal: { style: "thin", color: "#E5E7EB" },
  };
  history.getRange(`G${historyStartRow}:G${historyEndRow}`).conditionalFormats.add("containsText", {
    text: "Completed", format: { fill: "#DCFCE7", font: { color: "#166534", bold: true } },
  });
  history.getRange(`G${historyStartRow}:G${historyEndRow}`).conditionalFormats.add("containsText", {
    text: "Failed", format: { fill: "#FEE2E2", font: { color: "#991B1B", bold: true } },
  });
  history.tables.add(`A4:N${historyEndRow}`, true, "WithdrawalHistoryTable").style = "TableStyleMedium2";
}
history.freezePanes.freezeRows(4);
history.getRange("A:A").format.columnWidth = 21;
history.getRange("B:B").format.columnWidth = 21;
history.getRange("C:C").format.columnWidth = 10;
history.getRange("D:E").format.columnWidth = 15;
history.getRange("F:I").format.columnWidth = 16;
history.getRange("J:M").format.columnWidth = 25;
history.getRange("N:N").format.columnWidth = 36;
history.getRange(`N${historyStartRow}:N${historyEndRow}`).format.wrapText = false;

sources.mergeCells("A1:D1");
sources.getRange("A1:D1").values = [["Sources & Audit Notes"]];
sources.getRange("A1:D1").format = {
  fill: "#0B1F3A", font: { bold: true, color: "#FFFFFF", size: 16 },
};
sources.getRange("A3:D3").values = [["Item", "Value", "Source", "Notes"]];
sources.getRange("A3:D3").format = {
  fill: "#F0B90B", font: { bold: true, color: "#111827" },
};
sources.getRange("A4:D8").values = [
  ["Endpoint", "/sapi/v1/capital/withdraw/history", "https://developers.binance.com/en/docs/catalog/core-trading-wallet/api/rest-api/capital#withdraw-history", "Official signed USER_DATA endpoint"],
  ["Retrieval timestamp", new Date(payload.retrieved_at), "Binance API", "UTC"],
  ["Requested period", `${payload.source_start} to ${payload.source_end}`, "Binance API", "Consecutive 89-day windows"],
  ["API requests", payload.request_count, "Local retrieval log", "Pages of up to 1,000 records; deduplicated by withdrawal ID"],
  ["Privacy", "Masked export", "Local processing", "No API credentials stored; destination and transaction identifiers masked"],
];
sources.getRange("B5:B5").format.numberFormat = "yyyy-mm-dd hh:mm:ss";
sources.getRange("A3:D8").format.borders = { insideHorizontal: { style: "thin", color: "#E2E8F0" } };
sources.getRange("A:A").format.columnWidth = 22;
sources.getRange("B:B").format.columnWidth = 38;
sources.getRange("C:C").format.columnWidth = 72;
sources.getRange("D:D").format.columnWidth = 46;
sources.getRange("A3:D8").format.wrapText = true;

await fs.mkdir(outputDir, { recursive: true });
const summaryPreview = await workbook.render({ sheetName: "Summary", autoCrop: "all", scale: 1.5, format: "png" });
await fs.writeFile(path.join(outputDir, "summary_preview.png"), new Uint8Array(await summaryPreview.arrayBuffer()));
const historyPreview = await workbook.render({ sheetName: "Withdrawal History", range: "A1:N18", scale: 1, format: "png" });
await fs.writeFile(path.join(outputDir, "history_preview.png"), new Uint8Array(await historyPreview.arrayBuffer()));
const sourcesPreview = await workbook.render({ sheetName: "Sources & Notes", autoCrop: "all", scale: 1.25, format: "png" });
await fs.writeFile(path.join(outputDir, "sources_preview.png"), new Uint8Array(await sourcesPreview.arrayBuffer()));

const inspectSummary = await workbook.inspect({
  kind: "table", range: `Summary!A1:E${9 + Math.max(assets.length, 1)}`,
  include: "values,formulas", tableMaxRows: 40, tableMaxCols: 8,
});
console.log(inspectSummary.ndjson);
const errors = await workbook.inspect({
  kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan",
});
console.log(errors.ndjson);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.join(outputDir, "binance_withdrawal_history.xlsx"));
console.log(JSON.stringify({ records: records.length, assets: assets.length, workbook: path.join(outputDir, "binance_withdrawal_history.xlsx") }));
