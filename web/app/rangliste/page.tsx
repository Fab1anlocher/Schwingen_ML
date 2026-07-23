import { redirect } from "next/navigation";

// Rangliste und Schwinger zeigten praktisch dieselbe Elo-sortierte Liste
// doppelt — zusammengeführt in /schwinger (Suche + Filter + Rang + Profil).
export default function RanglisteRedirect() {
  redirect("/schwinger");
}
