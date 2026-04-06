import { useQuery } from "@tanstack/react-query";

import { ApiError, api } from "../../shared/api/client";

export function useSession() {
  return useQuery({
    queryKey: ["session"],
    queryFn: api.profile,
    retry: false,
    staleTime: 60_000,
    throwOnError: false,
    select: (data) => data,
    meta: { silent401: true },
  });
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}
