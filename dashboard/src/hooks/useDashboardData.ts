import { getAlerts } from "../api/alerts";
import { getReports } from "../api/reports";
import { getRoutes } from "../api/routes";
import { getSegments } from "../api/segments";
import { useApiResource } from "./useApiResource";

export function useDashboardData() {
  const segments = useApiResource(getSegments);
  const routes = useApiResource(getRoutes);
  const reports = useApiResource(getReports);
  const alerts = useApiResource(getAlerts);

  return { segments, routes, reports, alerts };
}
