/*
 * Names for the types generated from the OpenAPI contract by `npm run gen:api` into
 * ./schema.d.ts. DTOs are never declared by hand: they are aliases of the generated ones.
 */
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Credentials = Schemas["LoginRequest"];
export type TokenResponse = Schemas["TokenResponse"];

export type Taxonomy = Schemas["TaxonomyResponse"];
export type EquipmentRule = Schemas["EquipmentRule"];

export type ProfileOwner = Schemas["ProfileOwner"];
export type ProfilePut = Schemas["ProfilePut"];
export type SportItem = Schemas["SportItem"];
export type CapabilityItem = Schemas["CapabilityItem"];

export type SportCode = Schemas["SportCode"];
export type SkillLevel = Schemas["SkillLevel"];
export type CategoryCode = Schemas["CategoryCode"];
export type EquipmentCode = Schemas["EquipmentCode"];
export type DistrictCode = Schemas["DistrictCode"];

export type ValidationIssue = Schemas["ValidationError"];

export type MatchFeed = Schemas["MatchFeed"];
export type MatchItem = Schemas["MatchItem"];
export type MatchBreakdown = Schemas["MatchBreakdown"];
export type MatchMaxPoints = Schemas["MatchMaxPoints"];
export type MatchRankInfluence = Schemas["MatchRankInfluence"];
export type SearchRadius = Schemas["SearchRadius"];
export type DistanceBand = Schemas["DistanceBand"];
export type FunctionalLevel = Schemas["FunctionalLevel"];
export type RankInfluence = Schemas["RankInfluence"];
export type RankSource = Schemas["RankSource"];

export type ContactRequiredResponse = Schemas["ContactRequiredResponse"];
export type InvitationCreate =Schemas["InvitationCreate"];
export type InvitationIncoming = Schemas["InvitationIncoming"];
export type InvitationOutgoing = Schemas["InvitationOutgoing"];
export type InvitationOut = InvitationIncoming | InvitationOutgoing;
export type InvitationPartner = Schemas["InvitationPartner"];
export type InvitationStatus = Schemas["Status"];
export type InvitationDirection = Schemas["Direction"];
