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

-- One scan of many items (bags, merchant, journal) or one refresh of the window asks for the same contexts
-- again and again. Between BeginContextScan and EndContextScan they are built once and reused; every new scan
-- starts empty, so a gear, spec or setting change is picked up by the next scan. Scans may be nested: the
-- outermost one owns the cache. A change of the saved selection inside a scan drops what was built (ResetContextScan).
local contextScan = nil
local contextScanDepth = 0

function ns.BeginContextScan()
    contextScanDepth = contextScanDepth + 1
    if contextScanDepth == 1 then
        contextScan = {}
    end
end

function ns.EndContextScan()
    if contextScanDepth > 0 then
        contextScanDepth = contextScanDepth - 1
    end
    if contextScanDepth == 0 then
        contextScan = nil
    end
end

-- Outside an explicit scan the contexts are still reused within one frame of the game (GetTime does not move
-- inside a frame): code that asks again and again, such as every Best in Slot row asking for the active
-- tier, builds the profile once per frame, not once per ask. The next frame starts empty.
local frameScan, frameScanTime = nil, nil

function ns.ResetContextScan()
    if contextScan then
        contextScan = {}
    end
    frameScan, frameScanTime = nil, nil
end

function ns.GetContextScanCache()
    if contextScan then
        return contextScan
    end
    local now = GetTime and GetTime() or nil
    if not now then
        return nil
    end
    if frameScanTime ~= now then
        frameScan, frameScanTime = {}, now
    end
    return frameScan
end

function ns.GetEvaluationContext()
    local scan = ns.GetContextScanCache()
    if scan and scan.evaluation then
        return scan.evaluation
    end
    local context = BuildCurrentContext()
    if ns.LoadEvaluationProfile then
        context.profile = ns.LoadEvaluationProfile(context)
    end
    if scan then
        scan.evaluation = context
    end
    return context
end
