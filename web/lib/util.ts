export const MAX_COMPARE_SCHOOLS = 4;

export function slugify(name: string): string {
  return name.trim().toLowerCase().replace(/\s+/g, "-").replace(/[.,]/g, "");
}

export function resolveSchoolId(
  schoolId: string | undefined,
  schoolName: string,
): string {
  return schoolId ?? slugify(schoolName);
}

export function buildCompareHref(ids: readonly string[]): string {
  const q = new URLSearchParams();
  ids.forEach((id) => q.append("ids", id));
  return `/compare?${q.toString()}`;
}

export function parseCompareIds(search: string): string[] {
  const params = new URLSearchParams(search);
  return params
    .getAll("ids")
    .map((id) => id.trim())
    .filter(Boolean);
}

export function formatAed(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || Number.isNaN(amount)) {
    return "—";
  }
  return new Intl.NumberFormat("en-AE", {
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatFeeRange(
  minFee: number | null | undefined,
  maxFee: number | null | undefined,
): string {
  if (minFee == null && maxFee == null) return "—";
  if (minFee != null && maxFee != null && minFee !== maxFee) {
    return `AED ${formatAed(minFee)} – ${formatAed(maxFee)}`;
  }
  const value = minFee ?? maxFee;
  return `AED ${formatAed(value)}`;
}
