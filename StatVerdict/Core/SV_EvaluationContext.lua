local addonName, ns = ...

local DEFAULT_PROVIDER_KEY = "Generated"
local DEFAULT_PROVIDER_LABEL = "StatVerdict"

local function SafeCall(func, ...)
    if type(func) ~= "function" then return nil end
    local ok, a, b, c, d = pcall(func, ...)
    if ok then return a, b, c, d end
    return nil
end

local function GetHeroName(info)
    if type(info) == "table" then
        return info.name or info.heroTalentSpecName or info.heroSpecName
    end
    return type(info) == "string" and info or nil
end

local function GetCurrentHeroTalentName()
    local heroSpecID
    if C_ClassTalents and C_ClassTalents.GetActiveHeroTalentSpec then
        heroSpecID = SafeCall(C_ClassTalents.GetActiveHeroTalentSpec)
    end
    if not heroSpecID and C_ClassTalents and C_ClassTalents.GetActiveHeroTalentSpecID then
        heroSpecID = SafeCall(C_ClassTalents.GetActiveHeroTalentSpecID)
    end
    if not heroSpecID then return nil end

    if C_ClassTalents and C_ClassTalents.GetHeroTalentSpecInfo then
        local name = GetHeroName(SafeCall(C_ClassTalents.GetHeroTalentSpecInfo, heroSpecID))
        if name then return name end
    end
    if C_Traits and C_Traits.GetDefinitionInfo then
        return GetHeroName(SafeCall(C_Traits.GetDefinitionInfo, heroSpecID))
    end
    return nil
end

local function GetCurrentHeroSubTreeID()
    local heroSpecID
    if C_ClassTalents and C_ClassTalents.GetActiveHeroTalentSpec then
        heroSpecID = SafeCall(C_ClassTalents.GetActiveHeroTalentSpec)
    end
    if not heroSpecID and C_ClassTalents and C_ClassTalents.GetActiveHeroTalentSpecID then
        heroSpecID = SafeCall(C_ClassTalents.GetActiveHeroTalentSpecID)
    end
    return tonumber(heroSpecID)
end

local function BuildCurrentContext()
    local className, classFile = UnitClass("player")
    local specIndex = SafeCall(GetSpecialization)
    local specID, specName, _, _, role
    if specIndex then
        specID, specName, _, _, role = SafeCall(GetSpecializationInfo, specIndex)
    end

    return {
        providerKey = DEFAULT_PROVIDER_KEY,
        providerLabel = DEFAULT_PROVIDER_LABEL,
        classFile = classFile,
        className = className,
        specID = specID,
        specName = specName,
        role = role,
        heroTalentName = GetCurrentHeroTalentName(),
        heroSubTreeID = GetCurrentHeroSubTreeID(),
        source = "current_player_context",
    }
end

function ns.GetEvaluationContext()
    local context = BuildCurrentContext()
    if ns.LoadEvaluationProfile then
        context.profile = ns.LoadEvaluationProfile(context)
    end
    return context
end
