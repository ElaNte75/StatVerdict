local addonName, ns = ...

-- The Guide drawer: where the addon's stat priorities, Best in Slot lists and
-- stat targets come from. Everything is a 1:1 copy of the guides, never tuned
-- or corrected; this file holds the wording shown to the player and the stat
-- target tier choice, which the profile repository keeps and applies
-- (StatVerdictDB.statTargetBin).
--
-- The one player-visible line allowed to name the data sources lives here (the
-- NoDataSourceNamesShownTests test lists this file as the one exception).
local GUIDE = {
    title = "Guide",
    intro = "All guide information comes from Icy Veins and u.gg.",
}

-- Which guide stat target level is used. Kept by the repository
-- (StatVerdictDB.statTargetBin): exactly one of Auto or one tier, never two. The
-- saved keys stay auto/top20/top50/top80; the player sees Auto, then a tier,
-- listed Tier 1 to Tier 3 (Tier 3 is the most demanding). Auto picks the tier
-- from the character's own stats (see the repository).
local STAT_TARGET_BINS = {
    { key = "auto", label = "Auto", hint = "Recommended", meaning = "Follows your stats", auto = true },
    { key = "top80", label = "Tier 1", hint = "Comfortable", meaning = "Targets most players reach" },
    { key = "top50", label = "Tier 2", hint = "Realistic", meaning = "The stats of a typical player" },
    { key = "top20", label = "Tier 3", hint = "Demanding", meaning = "The best-equipped players" },
}
local DEFAULT_STAT_TARGET_BIN = "auto"

function ns.GetGuideInfo()
    return GUIDE
end

function ns.GetStatTargetBins()
    return STAT_TARGET_BINS
end

function ns.GetStatTargetBin(specKey)
    local repository = ns.ProfileRepository
    if repository and repository.GetStatTargetBin then
        return repository.GetStatTargetBin(specKey)
    end
    return DEFAULT_STAT_TARGET_BIN
end

-- Saves the stat target tier through the repository (which drops its cached
-- views), then redraws the audit and the bag markers. false for an unknown tier.
function ns.SetStatTargetBin(key, specKey)
    local repository = ns.ProfileRepository
    if not (repository and repository.SetStatTargetBin) then return false end
    if not repository.SetStatTargetBin(key, specKey) then return false end
    if ns.RequestStatAuditRefresh then ns.RequestStatAuditRefresh() end
    if ns.RefreshUpgradeIndicators then ns.RefreshUpgradeIndicators() end
    return true
end

-- What Auto says about the character (profile.autoInfo, set by the repository):
-- the line under "Auto" in the Guide drawer, the short label in the window title
-- bar, and the one-off notice after a move up. Fixed tiers say only their name.
local TIER_OF_BIN = { top80 = 1, top50 = 2, top20 = 3 }

local function Percent(progress)
    -- Rounded to the nearest (the window's Average Progress shows 58.5% where this says 59%), never 100% before it is reached.
    return math.max(0, math.min(99, math.floor((tonumber(progress) or 0) * 100 + 0.5)))
end

function ns.GetAutoTierSummary(profile)
    local info = type(profile) == "table" and profile.autoInfo or nil
    if type(info) ~= "table" then return nil end
    local level = tonumber(info.level) or 0
    if info.progress == nil then return "Follows your stats" end
    if level >= 3 then return "Tier 3 reached · top targets met" end
    if level <= 0 then return string.format("Starter · %d%% to Tier 1", Percent(info.progress)) end
    return string.format("Tier %d reached · %d%% to Tier %d", level, Percent(info.progress), level + 1)
end

-- The tier named in the title bar: Auto's reached tier and how far to the next one, or the
-- fixed tier chosen.
function ns.GetTierTitleLabel(profile)
    if type(profile) ~= "table" then return nil end
    local info = profile.autoInfo
    if type(info) == "table" then
        local level = tonumber(info.level) or 0
        if info.progress == nil then return "Auto" end
        if level >= 3 then return "Auto · Tier 3 · top targets met" end
        if level <= 0 then return string.format("Auto · Starter · %d%% to Tier 1", Percent(info.progress)) end
        return string.format("Auto · Tier %d · %d%% to Tier %d", level, Percent(info.progress), level + 1)
    end
    -- A fixed tier: its name and how far the next tier is (Tier 3: how much of its own targets is covered).
    local tier = TIER_OF_BIN[profile.statTargetBin]
    if not tier then return nil end
    local shares = profile.tierProgress
    if type(shares) ~= "table" then return "Tier " .. tier end
    if tier >= 3 then
        if shares[3] == nil then return "Tier 3" end
        return string.format("Tier 3 · %d%% of targets", math.max(0, math.min(100, math.floor(shares[3] * 100))))
    end
    if shares[tier + 1] == nil then return "Tier " .. tier end
    return string.format("Tier %d · %d%% to Tier %d", tier, Percent(shares[tier + 1]), tier + 1)
end

function ns.GetAutoTierNotice(profile)
    local repository = ns.ProfileRepository
    if not (repository and repository.GetAutoNotice) then return nil end
    local specKey = type(profile) == "table" and profile.specKey or nil
    local level = specKey and repository.GetAutoNotice(specKey) or nil
    if not level then return nil end
    return "You moved up to Tier " .. level .. "."
end

-- The cards under the guide text: Auto, then the guide's stat target tiers.
-- { title, options, selected, set(key) }.
-- The choice is the spec's own (Main Spec and Off Spec choose apart): `specKey` is the spec
-- of the build the drawer shows.
function ns.GetTargetChoice(specKey)
    return {
        title = "Stat targets",
        options = STAT_TARGET_BINS,
        selected = ns.GetStatTargetBin(specKey),
        set = function(key) return ns.SetStatTargetBin(key, specKey) end,
    }
end

-- Every goal (Mythic+, Raid, PvP) reads the same curated Best in Slot lists.
function ns.GetReferenceWording(goal)
    return {
        popular = false,
        button = "Best in Slot",
        base = "Best in Slot",
        main = "Main Spec Best in Slot",
        off = "Off Spec Best in Slot",
        progress = "BiS Progress",
        progressSuffix = "",
        tag = "BIS",
    }
end

-- The title of a spec in the main window. With an Off Spec set up (`choosable`), a checkbox
-- comes first: exactly one of Main Spec ("MAIN") and Off Spec ("OFF") is ticked, the one equal to
-- `view`, the build the whole window and the Guide drawer show. The box is an inline texture of
-- the game's own checkbox; the tick is drawn over it by the window (ns.SetSpecTitle).
local CHECKBOX_MARK = "|TInterface\\Buttons\\UI-CheckBox-Up:20:20:0:0|t "

function ns.SpecTitleText(text, which, view, choosable)
    text = tostring(text or "")
    if not choosable then return text end
    return CHECKBOX_MARK .. text
end

-- Whether the spec's checkbox is ticked.
function ns.IsSpecViewTicked(which, view, choosable)
    return choosable == true and view == which
end

-- "Stat targets · Main Spec": the Guide's choice says which build it is for.
function ns.GetTargetChoiceTitle(view)
    return "Stat targets · " .. (view == "OFF" and "Off Spec" or "Main Spec")
end
