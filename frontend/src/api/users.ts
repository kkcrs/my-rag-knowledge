import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  assignUserRoles as sdkAssignUserRoles,
  createUser as sdkCreateUser,
  deleteUser as sdkDeleteUser,
  listUsers as sdkListUsers,
  updateUser as sdkUpdateUser,
} from '@/client/sdk.gen'
import type { UserCreate, UserUpdate } from '@/client/types.gen'
import { usersListKey } from '@/api/queryKeys'

export function useUsersQuery(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: usersListKey(page, pageSize),
    queryFn: async () =>
      (await sdkListUsers({ query: { page, page_size: pageSize } })).data,
  })
}

export function useCreateUserMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: UserCreate) =>
      (await sdkCreateUser({ body: payload })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
    },
  })
}

export function useUpdateUserMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      ...body
    }: { id: string } & UserUpdate) =>
      (await sdkUpdateUser({ path: { user_id: id }, body })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
    },
  })
}

export function useAssignUserRolesMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      userId,
      roleIds,
    }: {
      userId: string
      roleIds: string[]
    }) =>
      (
        await sdkAssignUserRoles({
          path: { user_id: userId },
          body: { role_ids: roleIds },
        })
      ).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
    },
  })
}

export function useDeleteUserMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (userId: string) =>
      sdkDeleteUser({ path: { user_id: userId } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
    },
  })
}
