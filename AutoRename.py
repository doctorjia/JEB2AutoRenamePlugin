# -*- coding: utf-8 -*-

import string, sys
import re, collections

from com.pnfsoftware.jeb.client.api import IClientContext
# Source code error, using getEnginesContext
from com.pnfsoftware.jeb.client.api import IScript, IGraphicalClientContext
# Using run / executeAsync
from com.pnfsoftware.jeb.core import RuntimeProjectUtil
# Using getAddress
from com.pnfsoftware.jeb.core.actions import ActionRenameData
# Using findUnitsByType
from com.pnfsoftware.jeb.core.actions import Actions, ActionContext, ActionXrefsData, ActionTypeHierarchyData
# Using setNewName
from com.pnfsoftware.jeb.core.events import JebEvent, J
# Both classes
from com.pnfsoftware.jeb.core.output import AbstractUnitRepresentation, UnitRepresentationAdapter
# Using getDecompiler
from com.pnfsoftware.jeb.core.output.text import ITextDocument
# Both classes
from com.pnfsoftware.jeb.core.units.code import ICodeUnit, ICodeItem
from com.pnfsoftware.jeb.core.units.code.android import IDexUnit
# Using getClass, getMethods, getMethod, getField, getField / getSignature, getName, getItemId, getAddress
from com.pnfsoftware.jeb.core.units.code.java import IJavaSourceUnit, IJavaStaticField, IJavaNewArray, IJavaConstant, \
    IJavaCall, IJavaField, IJavaMethod, IJavaClass
# Using getClassElement / getField / / getMethod
# / getName(get field name), getSignature(get field signature), getType(get field type)
# / getName(get method name), getSignature(get field signature), getType(get method type)
from com.pnfsoftware.jeb.core.util import DecompilerHelper
from java.lang import Runnable


class JEB2AutoRename(IScript):
    def run(self, ctx):
        ctx.executeAsync("Running name detection...", AutoRename(ctx))
        print('Task complete.')


class AutoRename(Runnable):
    def __init__(self, cont):
        self.cont = cont

    def run(self):
        cont = self.cont
        engcont = cont.getEnginesContext()
        if not engcont:
            print("Engine is not working.")
            return

        project = engcont.getProjects()
        if not project:
            print("There is no running project.")
            return

        prj = project[0]

        self.codeUnit = RuntimeProjectUtil.findUnitsByType(prj, ICodeUnit, False)
        self.curIdx = 0
        bcUnits = []
        for unit in self.codeUnit:
            classes = unit.getClasses()
            if classes and unit.getName().lower() == 'bytecode':
                bcUnits.append(unit)
        targetUnit = bcUnits[0]
        self.targetUnit = targetUnit

        # Renaming classes
        cnt = 0
        for clz in targetUnit.getClasses():
            if badName(clz.getName(False)):
                newName = self.genName(clz)
                if not newName:
                    newName = uniqueName(cnt)
                else:
                    newName = uniqueName(cnt) + "_" + newName.split('/')[-1][:-1]
                self.rename(clz.getSignature(False), newName, 0)
                print("cnt is " + str(cnt) + "new name is " + str(newName))
                cnt += 1

        # Renaming fields
        cnt = 0
        for field in targetUnit.getFields():
            if badName(field.getName(False)):
                fieldType = field.getFieldType().getName(True)
                newName = fieldType + "_" + uniqueName(cnt)
                self.rename(field.getAddress(), newName, 1)
                print("cnt is " + str(cnt) + "new name is " + str(newName))
                cnt += 1

        # Renaming functions
        cnt = 0
        for fun in targetUnit.getMethods():
            if badName(fun.getName(False)):
                print(fun.getName(False))
                newName = '_'.join(map(lambda x: x.getName(True), fun.getParameterTypes())) + "_" + uniqueName(cnt)
                self.rename(fun.getAddress(), newName, 2)
                print("cnt is " + str(cnt) + "new name is " + str(newName))
                cnt += 1

    actCntx = None
    def rename(self, originName, newName, isClass):
        global actCntx
        if isClass == 0:
            clz = self.targetUnit.getClass(originName)
        elif isClass == 1:
            clz = self.targetUnit.getField(originName)
        else:
            clz = self.targetUnit.getMethod(originName)

        # Rename the class
        if clz:
            actCntx = ActionContext(self.targetUnit, Actions.RENAME, clz.getItemId(), clz.getAddress())
        actData = ActionRenameData()
        actData.setNewName(newName)

        if self.targetUnit.prepareExecution(actCntx, actData):
            # Do rename process
            try:
                bRlt = self.targetUnit.executeAction(actCntx, actData)
                if not bRlt:
                    print(u'Execute action fail!')
            except Exception, e:
                # Not using "Exception as e" here
                print(Exception, ":", e)

    def genName(self, clzElement):
        decomp = DecompilerHelper.getDecompiler(self.targetUnit)
        javaunit = decomp.decompile(clzElement.getAddress())
        clzElement = javaunit.getClassElement()

        if not badName(clzElement.getName()):
            return clzElement.getName()
        son = clzElement.getImplementedInterfaces()
        father = []
        father.extend(son)
        # son returns after reaching bottom

        father.append(clzElement.getSupertype())

        for fatherCon in father:
            sig = fatherCon.getSignature()
            if sig == "Ljava/lang/Object;":
                continue
            if not badName(sig):
                return sig
            fixType = self.targetUnit.getClass(sig)
            if fixType:
                guessedName = self.genName(fixType)
                if guessedName:
                    return guessedName
            else:
                return sig
        return None

def badName(self):
    if "/" in self != -1:
        self = self.split('/')[1:-1]
    elif len(self):
        if self[-1] == ';':
            self = self[1:-1]
    if len(self):
        for item in self:
            item.lower()
        listi = list(self)
        testi = set(listi)
    else:
        return False
    if len(testi) < 3:
        # You may change 3 to larger numbers if you encounter many methods under one class
        return True
    else:
        return False


def uniqueName(self):
    ret = ''
    while self / 26 != 0:
        ret += chr(ord('a') + self % 26)
        self /= 26
    ret += chr(ord('a') + self % 26)
    return ret.upper()
