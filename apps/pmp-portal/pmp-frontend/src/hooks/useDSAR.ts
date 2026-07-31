import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api } from '../services/api'
import type { DSARRequest } from '../types'

export function useDSARRequests() {
  return useQuery({
    queryKey: ['dsar'],
    queryFn: async () => (await api.get<{ requests: DSARRequest[] }>('/dsar/requests')).data,
  })
}

export function useSubmitDSAR() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { request_type: string; description?: string }) =>
      (await api.post('/dsar/request', body)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dsar'] })
      toast.success('Request submitted', {
        description: "We'll respond within 30 days and email you when it's ready.",
      })
    },
    onError: (err: { response?: { data?: { detail?: string } } }) =>
      toast.error(err.response?.data?.detail ?? 'Could not submit your request'),
  })
}
