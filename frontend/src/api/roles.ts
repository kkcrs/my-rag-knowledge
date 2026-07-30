import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createRole as sdkCreateRole,
  deleteRole as sdkDeleteRole,
  listRoles as sdkListRoles,
  updateRole as sdkUpdateRole,
} from '@/client/sdk.gen'
import type { RoleCreate, RoleUpdate } from '@/client/types.gen'
import { rolesListKey } from '@/api/queryKeys'

export function useRolesQuery() {
  return useQuery({
    queryKey: rolesListKey,
    queryFn: async () => (await sdkListRoles()).data,
  })
}

export function useCreateRoleMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: RoleCreate) =>
      (await sdkCreateRole({ body: payload })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: rolesListKey })
    },
  })
}

export function useUpdateRoleMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: string } & RoleUpdate) =>
      (await sdkUpdateRole({ path: { role_id: id }, body })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: rolesListKey })
    },
  })
}

export function useDeleteRoleMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (roleId: string) =>
      sdkDeleteRole({ path: { role_id: roleId } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: rolesListKey })
    },
  })
}
