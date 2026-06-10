import { fetchSchoolDetail } from "@/lib/api";
import { ErrorState } from "@/components/ErrorState";
import { Badge } from "@/components/ui/Badge";
import { DataTable } from "@/components/ui/DataTable";

export const dynamic = "force-dynamic";

export default async function SchoolDetailPage({
  params,
}: {
  params: { id: string };
}): Promise<React.ReactElement> {
  let detail;
  try {
    detail = await fetchSchoolDetail(params.id);
  } catch {
    return <ErrorState message="We couldn't load this school's details right now." />;
  }

  return (
    <article className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">{detail.school_name}</h1>
        <p className="mt-1 text-sm text-muted dark:text-muted-dark">{detail.location}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {detail.curriculums.map((c) => (
            <Badge key={c}>{c}</Badge>
          ))}
        </div>
      </header>

      <section>
        <h2 className="mb-2 font-semibold">Inspection ratings</h2>
        <ul className="space-y-1 text-sm">
          {detail.ratings
            .filter((r) => r.rating)
            .map((r) => (
              <li key={r.academic_year}>
                {r.academic_year}: <strong>{r.rating}</strong>
              </li>
            ))}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 font-semibold">Fees by grade</h2>
        <DataTable
          caption="Annual tuition fees by grade"
          headers={["Grade", "Annual tuition (AED)"]}
        >
          {detail.fees
            .filter((f) => f.grade)
            .map((f) => (
              <tr
                key={f.grade}
                className="border-b border-border dark:border-border-dark"
              >
                <td className="py-2">{f.grade}</td>
                <td className="py-2">{f.tuition_fee.toLocaleString()}</td>
              </tr>
            ))}
        </DataTable>
      </section>
    </article>
  );
}
