import type { Direction, UploadStatus } from "./types";

// A hu-HU alapból a négyjegyű számot nem tagolja ("5465"), ezért mindig.
export const hufFmt = new Intl.NumberFormat("hu-HU", { maximumFractionDigits: 0, useGrouping: "always" });
export const amountFmt = new Intl.NumberFormat("hu-HU", { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: "always" });
export const rateFmt = new Intl.NumberFormat("hu-HU", { minimumFractionDigits: 2, maximumFractionDigits: 4, useGrouping: "always" });

export const STATUS_LABEL: Record<UploadStatus, string> = {
  ok: "Rendben",
  figyelmeztetes: "Figyelmeztetés",
  duplikalt: "Már szerepel",
  hiba: "Hiba",
};

export const DIRECTION_LABEL: Record<Direction, string> = { bejovo: "Bejövő", kimeno: "Kimenő" };

export const formatHuf = (v: number): string => `${hufFmt.format(v)} Ft`;

export const formatAmount = (value: string, currency: string): string =>
  `${(currency === "HUF" ? hufFmt : amountFmt).format(Number(value))} ${currency}`;
