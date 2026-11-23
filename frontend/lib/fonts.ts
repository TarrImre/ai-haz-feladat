import { Public_Sans } from "next/font/google";

// latin-ext az ő, ű miatt kell.
export const publicSans = Public_Sans({ subsets: ["latin", "latin-ext"], weight: ["400", "500", "600"], display: "swap" });
