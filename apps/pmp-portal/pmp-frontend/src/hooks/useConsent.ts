import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api } from '../services/api'
import type { HistoryEntry, PurposeGroup } from '../types'

export function usePreferenceCentre() {
  return useQuery({
    queryKey: ['preferences'],
    queryFn: async () => (await api.get<{ purposes: PurposeGroup[] }>('/preference-center')).data,
  })
}

export function useUpdatePreferences() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (preferences: { purpose: string; channel: string; granted: boolean }[]) =>
      (await api.put('/preference-center', { preferences })).data,
    onSuccess: (data: { applied: number; errors: { error: string }[] }) => {
      qc.invalidateQueries({ queryKey: ['preferences'] })
      qc.invalidateQueries({ queryKey: ['history'] })
      if (data.errors?.length) {
        toast.error(data.errors[0].error)
      } else {
        toast.success('Preferences saved', {
          description: 'Syncing to connected systems now.',
        })
      }
    },
    onError: () => toast.error("Couldn't save your preferences. Please try again."),
  })
}

export function useConsentHistory(days = 365) {
  return useQuery({
    queryKey: ['history', days],
    queryFn: async () => (await api.get<{ history: HistoryEntry[] }>(`/consent/history?days=${days}`)).data,
  })
}
