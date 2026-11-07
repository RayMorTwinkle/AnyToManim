// Offline macOS Vision OCR. Input: JSON array of frame paths; output: text per frame.
import Foundation
import Vision
import Darwin

do {
    let input = FileHandle.standardInput.readDataToEndOfFile()
    let paths = try JSONDecoder().decode([String].self, from: input)
    var output = [[String]]()
    for path in paths {
        let lines: [String] = try autoreleasepool {
            let request = VNRecognizeTextRequest()
            request.recognitionLevel = .accurate
            request.recognitionLanguages = ["zh-Hant", "zh-Hans", "en-US"]
            request.usesLanguageCorrection = false
            let handler = VNImageRequestHandler(url: URL(fileURLWithPath: path))
            do {
                try handler.perform([request])
            } catch {
                // Try CPU if the CLI sandbox cannot access GPU/Neural Engine.
                request.usesCPUOnly = true
                try handler.perform([request])
            }
            return (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
        }
        output.append(lines)
    }
    FileHandle.standardOutput.write(try JSONEncoder().encode(output))
} catch {
    let detail = error as NSError
    FileHandle.standardError.write(Data("\(detail.domain) (\(detail.code)): \(detail)\n".utf8))
    exit(1)
}
