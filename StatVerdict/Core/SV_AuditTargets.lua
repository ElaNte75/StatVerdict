local addonName, ns = ...

function ns.ResolveStatAuditProfileID(context, profile)
    if type(profile) == "table" and type(profile.id) == "string" and profile.id ~= "" then
        return profile.id
    end

    local specID = context and context.specID
    local specKey = specID and ns.GetStatVerdictSpecKeyBySpecID and ns.GetStatVerdictSpecKeyBySpecID(specID)
    return specKey
end
