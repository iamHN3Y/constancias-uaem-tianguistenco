import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

/** Sesión actual. `enabled: false` (vía retry:false) para no reintentar 401 en bucle. */
export function useSession() {
  return useQuery({
    queryKey: ["session"],
    queryFn: api.session,
    retry: false,
    staleTime: 30_000,
  });
}
