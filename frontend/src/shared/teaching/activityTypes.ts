export interface ActivityDraft {centers:[number|null,number|null];stepOrder:string[];datasetId:string|null;features:string[];note:string;question:string;exploration?:{counts:[number|null,number|null];description:string};roundCenters?:Record<string,(number|null)[]>;answers:{counts:[number|null,number|null];centers:[number|null,number|null]}}

export const activityIds=['group_books','explain_algorithm','explore_2d'] as const
export type ActivityId=typeof activityIds[number]
export interface ActivityDefinition {id:ActivityId;number:number;title:string;goal:string;introduction:string;pending:string;guidance:string;suggestions:string[];topic:string}
