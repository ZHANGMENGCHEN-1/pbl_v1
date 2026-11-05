export interface Config { model: string; system_prompt: string; temperature: number; weather: { enabled: boolean; units: 'celsius' | 'fahrenheit' }; astronomy: { enabled: boolean; equipment: 'naked_eye' | 'binoculars' | 'telescope' } }
export type NodeId = 'brain' | 'weather' | 'astronomy'
export type { Trace } from "../../shared/types"
export interface Run { id: string; input: string; status: string; created: string; finished: string | null }
export interface Project { id: string; name: string; subtitle: string; description: string; objectives: string[]; models: string[]; steps: { title: string; duration: string; tag: string; body: string; instruction: string }[]; tools: Record<'weather' | 'astronomy', { name: string; description: string; parameters: { name: string; type: string; description: string }[] }> }
