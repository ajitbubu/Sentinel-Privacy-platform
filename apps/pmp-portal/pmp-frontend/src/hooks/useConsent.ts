import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'

export function useConsents(status = 'granted') {
  return useQuery({
    queryKey: ['consents', status],
    queryFn: async () => (await api.get(`/consent?status=${status}`)).data,
  })
}

export function useWithdrawConsent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ consentId, reason }: { consentId: string; reason?: string }) =>
      (await api.post(`/consent/${consentId}/withdraw`, { reason })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['consents'] }),
  })
}

export function usePreferenceCenter() {
  return useQuery({
    queryKey: ['preference-center'],
    queryFn: async () => (await api.get('/preference-center')).data,
  })
}
