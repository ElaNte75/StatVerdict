local addonName, ns = ...

local function IsArray(t)
    if type(t) ~= "table" then
        return false
    end
    local count = 0
    for k in pairs(t) do
        if type(k) ~= "number" or k < 1 or math.floor(k) ~= k then
            return false
        end
        count = count + 1
    end
    if count == 0 then
        -- Ambiguous in Lua; prefer object so stats={} stays {}.
        return false
    end
    for i = 1, count do
        if t[i] == nil then
            return false
        end
    end
    return true
end

local function EscapeJsonString(s)
    s = tostring(s or "")
    s = s:gsub("\\", "\\\\")
    s = s:gsub("\"", "\\\"")
    s = s:gsub("\n", "\\n")
    s = s:gsub("\r", "\\r")
    s = s:gsub("\t", "\\t")
    return s
end

local function EncodeJson(value)
    local t = type(value)
    if value == nil then
        return "null"
    elseif t == "boolean" then
        return value and "true" or "false"
    elseif t == "number" then
        if value ~= value or value == math.huge or value == -math.huge then
            return "null"
        end
        return tostring(value)
    elseif t == "string" then
        return "\"" .. EscapeJsonString(value) .. "\""
    elseif t ~= "table" then
        return "null"
    end

    if IsArray(value) then
        local parts = {}
        for i = 1, #value do
            parts[#parts + 1] = EncodeJson(value[i])
        end
        return "[" .. table.concat(parts, ",") .. "]"
    end

    local parts = {}
    local keys = {}
    for k in pairs(value) do
        keys[#keys + 1] = tostring(k)
    end
    table.sort(keys)
    for _, k in ipairs(keys) do
        parts[#parts + 1] = "\"" .. EscapeJsonString(k) .. "\":" .. EncodeJson(value[k])
    end
    return "{" .. table.concat(parts, ",") .. "}"
end

local B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

local function EncodeBase64(data)
    local out = {}
    local len = #data
    local i = 1
    while i <= len do
        local a = string.byte(data, i) or 0
        local b = string.byte(data, i + 1) or 0
        local c = string.byte(data, i + 2) or 0
        local n = a * 65536 + b * 256 + c
        local n1 = math.floor(n / 262144) % 64
        local n2 = math.floor(n / 4096) % 64
        local n3 = math.floor(n / 64) % 64
        local n4 = n % 64
        if i + 1 > len then
            out[#out + 1] = B64:sub(n1 + 1, n1 + 1) .. B64:sub(n2 + 1, n2 + 1) .. "=="
        elseif i + 2 > len then
            out[#out + 1] = B64:sub(n1 + 1, n1 + 1) .. B64:sub(n2 + 1, n2 + 1) .. B64:sub(n3 + 1, n3 + 1) .. "="
        else
            out[#out + 1] = B64:sub(n1 + 1, n1 + 1) .. B64:sub(n2 + 1, n2 + 1) .. B64:sub(n3 + 1, n3 + 1) .. B64:sub(n4 + 1, n4 + 1)
        end
        i = i + 3
    end
    return table.concat(out)
end

-- WoW SavedVariables hate mega-strings; split into chunks.
local CHUNK_SIZE = 40000

function ns.EncodeExportPayload(profileData)
    local json = EncodeJson(profileData)
    local b64 = EncodeBase64(json)
    local chunks = {}
    for i = 1, #b64, CHUNK_SIZE do
        chunks[#chunks + 1] = b64:sub(i, i + CHUNK_SIZE - 1)
    end
    return {
        format = "json-b64-v1",
        jsonBytes = #json,
        b64Bytes = #b64,
        chunkCount = #chunks,
        chunks = chunks,
    }
end

ns.EncodeJson = EncodeJson
